#!/usr/bin/env python3
"""
Pipeline worker: skills table -> GitHub artifact fetch -> Supabase Storage + DB.

Usage:
  python scripts/scrape_github_skill_repo.py --limit 25
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import mimetypes
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.core.db import (  # noqa: E402
    db_enqueue_job,
    db_get_skills_with_repo_urls,
    db_insert_skill_artifacts,
    db_upsert_repo_source,
    get_supabase_client,
)
from server.core.storage import upload_bytes  # noqa: E402
from server.fetchers.github_skill_repo_scraper import parse_github_repo_url  # noqa: E402


LOGGER = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
PARSE_VERSION = "v1"
DEFAULT_BUCKET = "skill-artifacts"
DEFAULT_MAX_FILES = 50
DEFAULT_MAX_TOTAL_BYTES = 5 * 1024 * 1024
GITHUB_FILE_RE = re.compile(r"^[A-Za-z0-9._/\- ]+$")


@dataclass(slots=True)
class FetchedFile:
    path: str
    content: bytes
    size: int
    sha256: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch GitHub skill artifacts and store metadata in Supabase."
    )
    parser.add_argument("--limit", type=int, default=25, help="Max skills to process.")
    parser.add_argument("--offset", type=int, default=0, help="Offset for skills table scan.")
    parser.add_argument(
        "--recent-only",
        action="store_true",
        help="Only include skills seen or scraped within --recent-days.",
    )
    parser.add_argument(
        "--recent-days",
        type=int,
        default=7,
        help="Time window for --recent-only filter.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=DEFAULT_MAX_FILES,
        help="Max files fetched per skill.",
    )
    parser.add_argument(
        "--max-total-bytes",
        type=int,
        default=DEFAULT_MAX_TOTAL_BYTES,
        help="Max total bytes fetched per skill.",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="GitHub request timeout.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser.parse_args()


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SkillLens artifact worker (+https://github.com/yourusername/skilllens)",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_probably_binary(path: str, content: bytes) -> bool:
    blocked_ext = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".pdf",
        ".zip",
        ".gz",
        ".tar",
        ".mp3",
        ".mp4",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".exe",
        ".dll",
        ".bin",
    }
    suffix = Path(path).suffix.lower()
    if suffix in blocked_ext:
        return True
    return b"\x00" in content


def sanitize_relative_path(path: str) -> str:
    normalized = path.strip("/").replace("\\", "/")
    normalized = re.sub(r"/+", "/", normalized)
    if ".." in normalized.split("/"):
        raise ValueError(f"Unsafe relative path: {path}")
    if not normalized or not GITHUB_FILE_RE.match(normalized):
        raise ValueError(f"Invalid relative path: {path}")
    return normalized


def detect_content_type(path: str) -> str:
    guessed, _encoding = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def list_tree_paths(
    client: httpx.Client,
    owner: str,
    repo: str,
) -> tuple[str, list[dict[str, Any]], set[str]]:
    repo_payload = github_get_json(client, f"{GITHUB_API_BASE}/repos/{owner}/{repo}")
    default_branch = str(repo_payload.get("default_branch") or "").strip()
    if not default_branch:
        raise RuntimeError(f"Missing default branch for {owner}/{repo}")

    tree_payload = github_get_json(
        client,
        f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1",
    )
    tree = tree_payload.get("tree") or []
    if not isinstance(tree, list):
        raise RuntimeError(f"Invalid tree payload for {owner}/{repo}")
    blob_paths = {
        str(entry.get("path") or "")
        for entry in tree
        if entry.get("type") == "blob" and entry.get("path")
    }
    return default_branch, tree, blob_paths


def locate_skill_md_path(skill_slug: str, blob_paths: set[str]) -> str | None:
    candidates = [
        f"{skill_slug}/SKILL.md",
        f"skills/{skill_slug}/SKILL.md",
        f"{skill_slug}/skill.md",
        f"skills/{skill_slug}/skill.md",
    ]
    for path in candidates:
        if path in blob_paths:
            return path

    skill_md_any = [p for p in blob_paths if Path(p).name.lower() == "skill.md"]
    if len(skill_md_any) == 1:
        return skill_md_any[0]

    slug_lower = skill_slug.lower()
    for path in sorted(skill_md_any):
        if Path(path).parent.name.lower() == slug_lower:
            return path
    return None


def select_candidate_paths(
    skill_md_path: str,
    blob_paths: set[str],
    max_files: int,
) -> list[str]:
    selected: set[str] = {skill_md_path}
    skill_dir = str(Path(skill_md_path).parent).replace("\\", "/")
    if skill_dir == ".":
        skill_dir = ""

    manifests = [
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "pnpm-lock.yaml",
        "package-lock.json",
    ]
    for name in manifests:
        if name in blob_paths:
            selected.add(name)
        if skill_dir:
            nested = f"{skill_dir}/{name}"
            if nested in blob_paths:
                selected.add(nested)

    if skill_dir:
        for path in sorted(blob_paths):
            if len(selected) >= max_files:
                break
            if not path.startswith(f"{skill_dir}/"):
                continue
            if path in selected:
                continue
            selected.add(path)

    return sorted(selected)[:max_files]


def fetch_one_file(
    client: httpx.Client,
    owner: str,
    repo: str,
    ref: str,
    repo_path: str,
) -> FetchedFile:
    payload = github_get_json(
        client,
        f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{repo_path}?ref={ref}",
    )
    if payload.get("type") != "file":
        raise RuntimeError(f"Non-file path skipped: {repo_path}")
    if payload.get("encoding") != "base64":
        raise RuntimeError(f"Unexpected encoding for {repo_path}")

    encoded = str(payload.get("content") or "")
    content = base64.b64decode(encoded, validate=False)
    if is_probably_binary(repo_path, content):
        raise RuntimeError(f"Binary file skipped: {repo_path}")

    file_sha = hashlib.sha256(content).hexdigest()
    return FetchedFile(
        path=sanitize_relative_path(repo_path),
        content=content,
        size=len(content),
        sha256=file_sha,
    )


def github_get_json(client: httpx.Client, url: str, attempts: int = 4) -> dict[str, Any]:
    """Fetch JSON from GitHub with light retry logic for transient errors."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = client.get(url)
            status = response.status_code
            if status >= 500 or status in {403, 429}:
                raise RuntimeError(f"GitHub transient status {status} for {url}")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError(f"Unexpected JSON payload type for {url}")
            return payload
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= attempts:
                break
            sleep_s = min(8.0, 0.8 * (2 ** (attempt - 1)))
            time.sleep(sleep_s)
    raise RuntimeError(f"GitHub request failed after retries: {last_error}") from last_error


def compute_artifact_hash(files: list[FetchedFile]) -> str:
    digest = hashlib.sha256()
    for entry in sorted(files, key=lambda item: item.path):
        digest.update(entry.path.encode("utf-8"))
        digest.update(b"\n")
        digest.update(entry.content)
        digest.update(b"\n")
    return digest.hexdigest()


def build_manifest(skill_id: str, artifact_hash: str, files: list[FetchedFile]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for entry in sorted(files, key=lambda item: item.path):
        object_key = f"skills/{skill_id}/{artifact_hash}/{entry.path}"
        manifest.append(
            {
                "path": entry.path,
                "object_key": object_key,
                "sha256": entry.sha256,
                "bytes": entry.size,
            }
        )
    return manifest


def get_repo_source_attempt(repository_url: str) -> int:
    response = (
        get_supabase_client()
        .table("repo_sources")
        .select("attempt_count")
        .eq("repository_url", repository_url)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        return 1
    return int(rows[0].get("attempt_count") or 0) + 1


def get_artifact_attempt(skill_id: str, artifact_hash: str) -> int:
    response = (
        get_supabase_client()
        .table("skill_artifacts")
        .select("attempt_count")
        .eq("skill_id", skill_id)
        .eq("artifact_hash", artifact_hash)
        .eq("parse_version", PARSE_VERSION)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        return 1
    return int(rows[0].get("attempt_count") or 0) + 1


def find_existing_artifact(skill_id: str, artifact_hash: str) -> dict[str, Any] | None:
    response = (
        get_supabase_client()
        .table("skill_artifacts")
        .select("id,artifact_hash,fetch_status")
        .eq("skill_id", skill_id)
        .eq("artifact_hash", artifact_hash)
        .eq("parse_version", PARSE_VERSION)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def mark_repo_source_finished(
    repo_source_id: str,
    status: str,
    error: str | None = None,
    default_branch: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "fetch_status": status,
        "last_error": error,
        "last_fetched_at": now_iso(),
        "updated_at": now_iso(),
    }
    if default_branch:
        payload["default_branch"] = default_branch
    get_supabase_client().table("repo_sources").update(payload).eq("id", repo_source_id).execute()


def upsert_failed_artifact(
    skill_id: str,
    repo_source_id: str,
    repo_skill_path: str | None,
    error: str,
    bucket_name: str,
) -> None:
    failed_hash = hashlib.sha256(f"failed:{skill_id}:{repo_source_id}:{PARSE_VERSION}".encode()).hexdigest()
    attempt = get_artifact_attempt(skill_id, failed_hash)
    storage_prefix = f"skills/{skill_id}/{failed_hash}"
    db_insert_skill_artifacts(
        {
            "skill_id": skill_id,
            "repo_source_id": repo_source_id,
            "repo_skill_path": repo_skill_path,
            "parse_version": PARSE_VERSION,
            "artifact_hash": failed_hash,
            "bucket_name": bucket_name,
            "storage_prefix": storage_prefix,
            "files_manifest": [],
            "fetch_status": "failed",
            "attempt_count": attempt,
            "last_error": error,
            "fetched_at": now_iso(),
        }
    )


def process_skill(
    client: httpx.Client,
    skill_row: dict[str, Any],
    bucket_name: str,
    max_files: int,
    max_total_bytes: int,
) -> dict[str, Any]:
    skill_id = str(skill_row["id"])
    repository_url = str(skill_row["repository_url"]).strip()
    if not repository_url:
        return {"skill_id": skill_id, "status": "skipped", "reason": "missing_repository_url"}

    owner = str(skill_row.get("owner") or "").strip()
    repo = str(skill_row.get("repo") or "").strip()
    skill_slug = str(skill_row.get("skill_slug") or "").strip()
    if not owner or not repo:
        owner, repo = parse_github_repo_url(repository_url)
    if not skill_slug:
        skill_slug = repo

    repo_attempt = get_repo_source_attempt(repository_url)
    repo_source = db_upsert_repo_source(
        repository_url=repository_url,
        provider="github",
        owner=owner,
        repo=repo,
        fetch_status="running",
        last_error=None,
        attempt_count=repo_attempt,
    )
    repo_source_id = str(repo_source["id"])

    try:
        default_branch, _tree, blob_paths = list_tree_paths(client, owner, repo)
        skill_md_path = locate_skill_md_path(skill_slug, blob_paths)
        if not skill_md_path:
            raise RuntimeError(f"Unable to locate SKILL.md for slug={skill_slug}")

        candidate_paths = select_candidate_paths(skill_md_path, blob_paths, max_files=max_files)

        fetched: list[FetchedFile] = []
        total_bytes = 0
        for repo_path in candidate_paths:
            if len(fetched) >= max_files:
                break
            file_obj = fetch_one_file(client, owner, repo, default_branch, repo_path)
            if total_bytes + file_obj.size > max_total_bytes:
                LOGGER.warning(
                    "Reached byte cap for skill_id=%s before %s", skill_id, file_obj.path
                )
                break
            fetched.append(file_obj)
            total_bytes += file_obj.size

        if not fetched:
            raise RuntimeError("No text artifacts fetched")

        artifact_hash = compute_artifact_hash(fetched)
        existing = find_existing_artifact(skill_id, artifact_hash)
        if existing:
            artifact_id = str(existing["id"])
            db_enqueue_job(
                job_type="analyze",
                status="queued",
                skill_id=skill_id,
                repo_source_id=repo_source_id,
                artifact_id=artifact_id,
                payload={"analysis_version": "a1"},
            )
            mark_repo_source_finished(
                repo_source_id,
                status="succeeded",
                default_branch=default_branch,
            )
            return {
                "skill_id": skill_id,
                "status": "unchanged",
                "artifact_id": artifact_id,
                "artifact_hash": artifact_hash,
                "files": len(fetched),
            }

        manifest = build_manifest(skill_id, artifact_hash, fetched)
        storage_prefix = f"skills/{skill_id}/{artifact_hash}"

        for entry, manifest_entry in zip(
            sorted(fetched, key=lambda item: item.path), manifest, strict=True
        ):
            object_key = str(manifest_entry["object_key"])
            try:
                upload_bytes(
                    bucket=bucket_name,
                    object_key=object_key,
                    content_bytes=entry.content,
                    content_type=detect_content_type(entry.path),
                )
            except Exception as upload_exc:  # noqa: BLE001
                message = str(upload_exc).lower()
                duplicate_hint = "already exists" in message or "duplicate" in message
                if not duplicate_hint:
                    raise

        artifact_attempt = get_artifact_attempt(skill_id, artifact_hash)
        artifact_row = db_insert_skill_artifacts(
            {
                "skill_id": skill_id,
                "repo_source_id": repo_source_id,
                "repo_skill_path": skill_md_path,
                "parse_version": PARSE_VERSION,
                "artifact_hash": artifact_hash,
                "bucket_name": bucket_name,
                "storage_prefix": storage_prefix,
                "files_manifest": manifest,
                "fetch_status": "succeeded",
                "attempt_count": artifact_attempt,
                "last_error": None,
                "fetched_at": now_iso(),
            }
        )
        artifact_id = str(artifact_row["id"])

        db_enqueue_job(
            job_type="analyze",
            status="queued",
            skill_id=skill_id,
            repo_source_id=repo_source_id,
            artifact_id=artifact_id,
            payload={"analysis_version": "a1"},
        )

        mark_repo_source_finished(
            repo_source_id,
            status="succeeded",
            default_branch=default_branch,
        )
        return {
            "skill_id": skill_id,
            "status": "succeeded",
            "artifact_id": artifact_id,
            "artifact_hash": artifact_hash,
            "files": len(fetched),
            "storage_prefix": storage_prefix,
        }
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
        mark_repo_source_finished(repo_source_id, status="failed", error=error)
        upsert_failed_artifact(
            skill_id=skill_id,
            repo_source_id=repo_source_id,
            repo_skill_path=None,
            error=error,
            bucket_name=bucket_name,
        )
        return {"skill_id": skill_id, "status": "failed", "error": error}


def run() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    recent_days = args.recent_days if args.recent_only else None
    skills = db_get_skills_with_repo_urls(
        limit=args.limit,
        offset=args.offset,
        recent_days=recent_days,
    )

    bucket_name = os.getenv("SUPABASE_STORAGE_BUCKET", DEFAULT_BUCKET)
    timeout = httpx.Timeout(args.timeout)
    headers = github_headers()

    summary = {
        "total": len(skills),
        "succeeded": 0,
        "unchanged": 0,
        "failed": 0,
        "skipped": 0,
    }
    results: list[dict[str, Any]] = []

    with httpx.Client(timeout=timeout, headers=headers) as client:
        for skill in skills:
            result = process_skill(
                client=client,
                skill_row=skill,
                bucket_name=bucket_name,
                max_files=args.max_files,
                max_total_bytes=args.max_total_bytes,
            )
            results.append(result)
            status = str(result.get("status", "failed"))
            if status in summary:
                summary[status] += 1
            else:
                summary["failed"] += 1
            print(json.dumps(result, ensure_ascii=False))

    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
