"""Supabase DB helpers for artifact ingestion and job enqueueing."""

from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, TYPE_CHECKING

from dotenv import load_dotenv


def _load_create_client() -> tuple[Any | None, Exception | None]:
    try:
        module = importlib.import_module("supabase")
        factory = getattr(module, "create_client", None)
        if callable(factory):
            return factory, None
        raise ImportError("`supabase.create_client` was not found.")
    except Exception as primary_exc:  # noqa: BLE001
        original_path = list(sys.path)
        previous_module = sys.modules.pop("supabase", None)
        repo_root = Path(__file__).resolve().parents[2]
        cwd = Path.cwd().resolve()
        imported_ok = False

        try:
            filtered_path: list[str] = []
            for entry in original_path:
                if not entry:
                    continue
                resolved = Path(entry).resolve()
                if resolved in {repo_root, cwd}:
                    continue
                filtered_path.append(entry)
            sys.path = filtered_path

            module = importlib.import_module("supabase")
            factory = getattr(module, "create_client", None)
            if callable(factory):
                imported_ok = True
                return factory, None
            raise ImportError("`supabase.create_client` was not found after fallback import.")
        except Exception as fallback_exc:  # noqa: BLE001
            return None, fallback_exc if fallback_exc else primary_exc
        finally:
            sys.path = original_path
            if not imported_ok and previous_module is not None:
                sys.modules["supabase"] = previous_module


create_client, _SUPABASE_IMPORT_ERROR = _load_create_client()

if TYPE_CHECKING:
    from supabase import Client
else:
    Client = Any


load_dotenv()

_client: Client | None = None
_client_lock = Lock()


def get_supabase_client() -> Client:
    """Return a singleton Supabase client."""
    global _client
    if _client is not None:
        return _client

    with _client_lock:
        if _client is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")
            if not url or not key:
                raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
            if create_client is None:
                raise RuntimeError(
                    "Supabase Python client is not available. Install server dependencies "
                    "with `python3 -m pip install -r server/requirements.txt`. "
                    f"Original import error: {_SUPABASE_IMPORT_ERROR}"
                )
            _client = create_client(url, key)
    return _client


def db_get_skills_with_repo_urls(
    limit: int,
    offset: int = 0,
    recent_days: int | None = None,
) -> list[dict[str, Any]]:
    """Read skill rows with repository URLs from the catalog table."""
    query = (
        get_supabase_client()
        .table("skills")
        .select("id,repository_url,owner,repo,skill_slug,last_seen_at,scraped_at")
        .not_.is_("repository_url", "null")
        .range(offset, offset + max(limit, 1) - 1)
    )
    if recent_days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=max(recent_days, 1))
        since_iso = since.replace(microsecond=0).isoformat()
        query = query.or_(f"last_seen_at.gte.{since_iso},scraped_at.gte.{since_iso}")
    response = query.execute()
    return response.data or []


def db_upsert_repo_source(
    repository_url: str,
    owner: str,
    repo: str,
    provider: str = "github",
    fetch_status: str | None = None,
    last_error: str | None = None,
    attempt_count: int | None = None,
) -> dict[str, Any]:
    """Upsert repo source row by repository URL."""
    payload: dict[str, Any] = {
        "repository_url": repository_url,
        "provider": provider,
        "owner": owner,
        "repo": repo,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    if fetch_status is not None:
        payload["fetch_status"] = fetch_status
    if last_error is not None:
        payload["last_error"] = last_error
    if attempt_count is not None:
        payload["attempt_count"] = attempt_count
    response = (
        get_supabase_client()
        .table("repo_sources")
        .upsert(payload, on_conflict="repository_url")
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else {}


def db_insert_skill_artifacts(record: dict[str, Any]) -> dict[str, Any]:
    """Upsert one skill_artifacts record by (skill_id, artifact_hash, parse_version)."""
    payload = dict(record)
    payload["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    response = (
        get_supabase_client()
        .table("skill_artifacts")
        .upsert(payload, on_conflict="skill_id,artifact_hash,parse_version")
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else {}


def db_enqueue_job(
    job_type: str,
    status: str,
    skill_id: str | None = None,
    repo_source_id: str | None = None,
    artifact_id: str | None = None,
    payload: dict[str, Any] | None = None,
    priority: int = 100,
) -> dict[str, Any]:
    """Insert one job when no queued or running duplicate exists."""
    table = get_supabase_client().table("analysis_jobs")
    if job_type == "fetch_artifacts" and skill_id:
        existing = (
            table.select("id")
            .eq("job_type", "fetch_artifacts")
            .in_("status", ["queued", "running"])
            .eq("skill_id", skill_id)
            .limit(1)
            .execute()
        )
        rows = existing.data or []
        if rows:
            return rows[0]
    if job_type == "analyze" and artifact_id:
        existing = (
            table.select("id")
            .eq("job_type", "analyze")
            .in_("status", ["queued", "running"])
            .eq("artifact_id", artifact_id)
            .limit(1)
            .execute()
        )
        rows = existing.data or []
        if rows:
            return rows[0]

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    response = table.insert(
        {
            "job_type": job_type,
            "status": status,
            "priority": priority,
            "skill_id": skill_id,
            "repo_source_id": repo_source_id,
            "artifact_id": artifact_id,
            "payload": payload or {},
            "run_after": now_iso,
            "updated_at": now_iso,
        }
    ).execute()
    rows = response.data or []
    return rows[0] if rows else {}


def db_get_skill_artifact_files(artifact_id: str) -> list[dict[str, Any]]:
    """Return files_manifest entries from one skill_artifacts row."""
    response = (
        get_supabase_client()
        .table("skill_artifacts")
        .select("files_manifest")
        .eq("id", artifact_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        return []
    manifest = rows[0].get("files_manifest")
    if not isinstance(manifest, list):
        return []
    return [item for item in manifest if isinstance(item, dict)]


def db_get_skill_artifact(artifact_id: str) -> dict[str, Any]:
    """Fetch one skill_artifacts row with storage details."""
    response = (
        get_supabase_client()
        .table("skill_artifacts")
        .select("id,skill_id,repo_source_id,bucket_name,storage_prefix,files_manifest")
        .eq("id", artifact_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else {}


def db_get_skill_text_content(skill_id: str) -> str:
    """Get the best available skill markdown/text from the skills table."""
    response = (
        get_supabase_client()
        .table("skills")
        .select("skill_md_rendered,skill_content")
        .eq("id", skill_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        return ""
    row = rows[0]
    rendered = row.get("skill_md_rendered")
    if isinstance(rendered, str) and rendered.strip():
        return rendered
    raw = row.get("skill_content")
    if isinstance(raw, str):
        return raw
    return ""


def db_update_skill_analysis_security(
    analysis_id: str,
    security_data: dict[str, Any],
    trust_badge: str | None = None,
    overall_score: float | None = None,
) -> None:
    """Write security_data payload and optional summary fields to one skill_analyses row."""
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload: dict[str, Any] = {"security_data": security_data, "updated_at": now_iso}
    if trust_badge is not None:
        payload["trust_badge"] = trust_badge
    if overall_score is not None:
        payload["overall_score"] = overall_score
    (
        get_supabase_client()
        .table("skill_analyses")
        .update(payload)
        .eq("id", analysis_id)
        .execute()
    )


def db_ensure_skill_analysis_for_artifact(
    artifact_row: dict[str, Any],
    analysis_version: str = "a1",
) -> dict[str, Any]:
    """Ensure one skill_analyses row exists for an artifact."""
    artifact_id = artifact_row.get("id")
    if not artifact_id:
        return {}
    existing = (
        get_supabase_client()
        .table("skill_analyses")
        .select("id")
        .eq("artifact_id", artifact_id)
        .eq("analysis_version", analysis_version)
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    if rows:
        return rows[0]

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = {
        "skill_id": artifact_row.get("skill_id"),
        "repo_source_id": artifact_row.get("repo_source_id"),
        "artifact_id": artifact_id,
        "analysis_version": analysis_version,
        "status": "running",
        "started_at": now_iso,
        "updated_at": now_iso,
    }
    inserted = get_supabase_client().table("skill_analyses").insert(payload).execute()
    inserted_rows = inserted.data or []
    return inserted_rows[0] if inserted_rows else {}


def db_claim_next_job(job_type: str = "analyze") -> dict[str, Any]:
    """Claim the next queued job and mark as running."""
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    queued = (
        get_supabase_client()
        .table("analysis_jobs")
        .select("id,job_type,status,artifact_id,skill_id,repo_source_id,payload")
        .eq("job_type", job_type)
        .eq("status", "queued")
        .lte("run_after", now_iso)
        .order("priority", desc=False)
        .order("created_at", desc=False)
        .limit(1)
        .execute()
    )
    rows = queued.data or []
    if not rows:
        return {}
    job = rows[0]
    (
        get_supabase_client()
        .table("analysis_jobs")
        .update({"status": "running", "started_at": now_iso, "updated_at": now_iso})
        .eq("id", job["id"])
        .eq("status", "queued")
        .execute()
    )
    refreshed = (
        get_supabase_client()
        .table("analysis_jobs")
        .select("id,job_type,status,artifact_id,skill_id,repo_source_id,payload")
        .eq("id", job["id"])
        .limit(1)
        .execute()
    )
    refreshed_rows = refreshed.data or []
    return refreshed_rows[0] if refreshed_rows else {}


def db_finish_job(job_id: str, status: str, error: str | None = None) -> None:
    """Mark job succeeded or failed."""
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload: dict[str, Any] = {
        "status": status,
        "finished_at": now_iso,
        "updated_at": now_iso,
    }
    if error:
        payload["last_error"] = error
    (
        get_supabase_client()
        .table("analysis_jobs")
        .update(payload)
        .eq("id", job_id)
        .execute()
    )


def db_update_skill_analysis_status(
    analysis_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update skill_analyses status and terminal timestamps."""
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload: dict[str, Any] = {"status": status, "updated_at": now_iso}
    if status in {"completed", "success", "succeeded", "failed"}:
        payload["completed_at"] = now_iso
    if error_message:
        payload["error_message"] = error_message
    (
        get_supabase_client()
        .table("skill_analyses")
        .update(payload)
        .eq("id", analysis_id)
        .execute()
    )


def db_enqueue_analyze_jobs_from_existing_artifacts(limit: int = 200) -> int:
    """Queue analyze jobs from existing succeeded artifacts missing security_data."""
    artifacts_resp = (
        get_supabase_client()
        .table("skill_artifacts")
        .select("id,skill_id,repo_source_id,fetch_status,updated_at")
        .in_("fetch_status", ["succeeded", "success"])
        .order("updated_at", desc=True)
        .limit(max(limit, 1))
        .execute()
    )
    artifacts = artifacts_resp.data or []
    enqueued = 0
    for artifact in artifacts:
        artifact_id = artifact.get("id")
        if not artifact_id:
            continue
        analysis_resp = (
            get_supabase_client()
            .table("skill_analyses")
            .select("id,status,security_data")
            .eq("artifact_id", artifact_id)
            .eq("analysis_version", "a1")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        analysis_rows = analysis_resp.data or []
        if analysis_rows:
            latest = analysis_rows[0]
            status = latest.get("status")
            if status in {"queued", "running"}:
                continue
            security_data = latest.get("security_data")
            if isinstance(security_data, dict) and security_data:
                continue
        job = db_enqueue_job(
            job_type="analyze",
            status="queued",
            skill_id=artifact.get("skill_id"),
            repo_source_id=artifact.get("repo_source_id"),
            artifact_id=artifact_id,
            payload={"analysis_version": "a1"},
        )
        if job.get("id"):
            enqueued += 1
    return enqueued
