"""GitHub skill-repo scraper with incremental local storage."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import random
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

LOGGER = logging.getLogger(__name__)

PARSE_VERSION = "github_skill_v1"
STATE_FILENAME = "state.json"
MAX_FILE_SIZE_BYTES = 1_000_000
DEFAULT_ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".sh",
    ".bash",
    ".yaml",
    ".yml",
    ".json",
    ".md",
    ".txt",
    ".toml",
    ".ini",
    ".cfg",
    ".dockerfile",
    ".sql",
}
DEFAULT_EXCLUDED_PATH_PARTS = {
    "node_modules",
    "dist",
    "build",
    ".git",
    "__pycache__",
    ".next",
    ".cache",
    ".venv",
    "venv",
    "target",
    "coverage",
}
DEFAULT_SKILL_MD_PATTERNS = [
    "{skill_slug}/SKILL.md",
    "skills/{skill_slug}/SKILL.md",
    "{skill_slug}/skill.md",
    "skills/{skill_slug}/skill.md",
]

GITHUB_API_BASE = "https://api.github.com"
GITHUB_URL_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/#?]+)")
GITHUB_BLOB_URL_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+)/blob/[^/]+/(.+)$", re.IGNORECASE
)
GITHUB_RAW_URL_RE = re.compile(
    r"^https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/[^/]+/(.+)$",
    re.IGNORECASE,
)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*]\(([^)]+)\)")
CODE_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
PATHISH_RE = re.compile(
    r"(?<![\w.-])(\.{1,2}/[^\s`\"'>)]+|[\w./-]+/[\w./-]+(?:\.[\w.-]+)?)"
)


class ScraperError(Exception):
    """Raised for recoverable scraper errors."""


class AsyncRateLimiter:
    """Token-interval rate limiter for async request pacing."""

    def __init__(self, rate_per_second: float) -> None:
        self.rate = max(rate_per_second, 0.001)
        self.interval = 1.0 / self.rate
        self._next_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        loop = asyncio.get_running_loop()
        async with self._lock:
            now = loop.time()
            wait_for = self._next_time - now
            if wait_for > 0:
                await asyncio.sleep(wait_for)
                now = loop.time()
            self._next_time = now + self.interval


@dataclass(slots=True)
class GitHubFile:
    path: str
    sha: str
    size: int
    download_url: str
    content: str
    content_hash: str
    fetched_at: str


def sha256_text(value: str) -> str:
    """Compute deterministic SHA-256 hash for UTF-8 text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_github_repo_url(repository_url: str) -> tuple[str, str]:
    """Parse owner/repo from a GitHub URL."""
    match = GITHUB_URL_RE.match((repository_url or "").strip())
    if not match:
        raise ValueError(f"Unsupported GitHub repository URL: {repository_url!r}")
    owner = match.group(1)
    repo = match.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def skill_state_key(owner: str, repo: str, skill_slug: str) -> str:
    """Build state-key path segment for one repo skill."""
    return f"{owner}/{repo}/{skill_slug}"


def sanitize_segment(value: str) -> str:
    """Create filesystem-safe path segment."""
    return re.sub(r"[^A-Za-z0-9._:-]+", "_", value)


def safe_output_path(base_dir: Path, relative_repo_path: str) -> Path:
    """Convert repo-relative path to safe nested filesystem path."""
    parts = [sanitize_segment(part) for part in relative_repo_path.strip("/").split("/") if part]
    if not parts:
        parts = ["_root_"]
    return base_dir.joinpath(*parts)


def load_state(state_path: Path) -> dict[str, Any]:
    """Load incremental scraper state file."""
    if not state_path.exists():
        return {"version": 1, "skills": {}}
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    """Persist incremental scraper state file."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_repo_path(path: str, base_dir: str = "") -> str | None:
    """Resolve repo path text to a normalized repo-relative path."""
    value = unquote((path or "").strip())
    if not value:
        return None
    if value.startswith("#"):
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return None

    value = value.split("?", 1)[0].split("#", 1)[0]
    if value.startswith("/"):
        candidate = value[1:]
    else:
        candidate = f"{base_dir}/{value}" if base_dir else value
    candidate = re.sub(r"/+", "/", candidate)

    stack: list[str] = []
    for piece in candidate.split("/"):
        if piece in {"", "."}:
            continue
        if piece == "..":
            if not stack:
                return None
            stack.pop()
            continue
        stack.append(piece)
    if not stack:
        return None
    return "/".join(stack)


def extract_paths_from_skill_md(
    skill_md_content: str,
    owner: str,
    repo: str,
    skill_md_path: str,
    allowed_extensions: set[str] | None = None,
) -> list[str]:
    """Extract repo-relative file paths from SKILL.md content."""
    allowed = {ext.lower() for ext in (allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS)}
    skill_dir = str(Path(skill_md_path).parent).replace("\\", "/")
    if skill_dir == ".":
        skill_dir = ""
    refs: set[str] = set()

    def maybe_add(candidate: str) -> None:
        normalized = normalize_repo_path(candidate, base_dir=skill_dir)
        if not normalized:
            return
        suffix = Path(normalized).suffix.lower()
        if suffix and suffix in allowed:
            refs.add(normalized)
            return
        name = Path(normalized).name.lower()
        if name == "dockerfile" or name.endswith(".dockerfile"):
            refs.add(normalized)
            return
        if suffix == "" and any(normalized.lower().endswith(ext) for ext in allowed):
            refs.add(normalized)

    owner_lower = owner.lower()
    repo_lower = repo.lower()

    for linked in MARKDOWN_LINK_RE.findall(skill_md_content):
        target = linked.strip().strip("<>").strip("\"'")
        if not target:
            continue
        blob_match = GITHUB_BLOB_URL_RE.match(target)
        if blob_match:
            if (
                blob_match.group(1).lower() == owner_lower
                and blob_match.group(2).lower() == repo_lower
            ):
                maybe_add(blob_match.group(3))
            continue
        raw_match = GITHUB_RAW_URL_RE.match(target)
        if raw_match:
            if (
                raw_match.group(1).lower() == owner_lower
                and raw_match.group(2).lower() == repo_lower
            ):
                maybe_add(raw_match.group(3))
            continue
        maybe_add(target)

    for block in CODE_BLOCK_RE.findall(skill_md_content):
        for candidate in PATHISH_RE.findall(block):
            maybe_add(candidate)

    for candidate in PATHISH_RE.findall(skill_md_content):
        maybe_add(candidate)

    refs.discard(skill_md_path)
    return sorted(refs)


def should_skip_by_extension(path: str, allowed_extensions: set[str]) -> bool:
    """Return true when file extension is not in allowed list."""
    lower = path.lower()
    name = Path(lower).name
    if name == "dockerfile":
        return False
    suffix = Path(lower).suffix
    if suffix in allowed_extensions:
        return False
    return not lower.endswith(".dockerfile")


def should_skip_by_size(size: int, max_file_size_bytes: int) -> bool:
    """Return true when file size exceeds configured cap."""
    return size < 0 or size > max_file_size_bytes


def is_probably_binary(path: str, content: bytes) -> bool:
    """Detect binary payload by extension and null-byte check."""
    lower = path.lower()
    blocked_ext = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".pdf",
        ".zip",
        ".gz",
        ".tar",
        ".mp4",
        ".mp3",
        ".wav",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".exe",
        ".dll",
        ".bin",
    }
    if Path(lower).suffix in blocked_ext:
        return True
    return b"\x00" in content


def locate_skill_md_path(
    tree_paths: set[str],
    skill_slug: str,
    repo_skill_count: int,
    patterns: list[str] | None = None,
) -> str | None:
    """Locate SKILL.md path by configured patterns and fallback search."""
    checks = patterns or list(DEFAULT_SKILL_MD_PATTERNS)
    for pattern in checks:
        candidate = pattern.format(skill_slug=skill_slug)
        if candidate in tree_paths:
            return candidate
    if repo_skill_count == 1 and "SKILL.md" in tree_paths:
        return "SKILL.md"
    if repo_skill_count == 1 and "skill.md" in tree_paths:
        return "skill.md"

    slug_lower = skill_slug.lower()
    for path in sorted(tree_paths):
        if Path(path).name.lower() != "skill.md":
            continue
        if Path(path).parent.name.lower() == slug_lower:
            return path
    return None


def decide_update_event(
    previous_state: dict[str, Any] | None,
    skill_md_sha: str,
    file_shas: dict[str, str],
) -> str:
    """Return NEW/UPDATED/UPDATED_FILE/UNCHANGED based on SHA deltas."""
    if previous_state is None:
        return "NEW"
    prev_skill_sha = previous_state.get("skill_md_sha")
    prev_files = previous_state.get("files", {})
    prev_file_shas = {path: meta.get("sha") for path, meta in prev_files.items()}
    if prev_skill_sha != skill_md_sha:
        return "UPDATED"
    if prev_file_shas == file_shas:
        return "UNCHANGED"
    return "UPDATED_FILE"


def list_skill_json_paths(input_dir: Path) -> list[Path]:
    """List prior scraper JSON records from input directory."""
    return sorted(p for p in input_dir.glob("*.json") if p.is_file())


def load_skill_records(input_dir: Path) -> list[dict[str, Any]]:
    """Load skills.sh records that include repository_url and skill_slug."""
    records: list[dict[str, Any]] = []
    for path in list_skill_json_paths(input_dir):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Skipping unreadable JSON %s: %s", path, exc)
            continue
        repository_url = str(payload.get("repository_url", "")).strip()
        skill_slug = str(payload.get("skill_slug", "")).strip()
        owner = str(payload.get("owner", "")).strip()
        repo = str(payload.get("repo", "")).strip()
        if not repository_url or not skill_slug:
            continue
        if not owner or not repo:
            try:
                owner, repo = parse_github_repo_url(repository_url)
            except ValueError:
                continue
        records.append(
            {
                "repository_url": repository_url,
                "owner": owner,
                "repo": repo,
                "skill_slug": skill_slug,
            }
        )
    return records


class GitHubSkillRepoScraper:
    """Scraper that fetches SKILL.md and related files from GitHub repositories."""

    def __init__(
        self,
        outdir: Path,
        concurrency: int = 5,
        rate_limit: float = 2.0,
        timeout_seconds: float = 20.0,
        max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
        allowed_extensions: set[str] | None = None,
        excluded_path_parts: set[str] | None = None,
        skill_md_patterns: list[str] | None = None,
    ) -> None:
        self.outdir = outdir
        self.state_path = outdir / STATE_FILENAME
        self.concurrency = max(1, concurrency)
        self.rate_limit = max(rate_limit, 0.1)
        self.timeout_seconds = timeout_seconds
        self.max_file_size_bytes = max_file_size_bytes
        self.allowed_extensions = {
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in (allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS)
        }
        self.excluded_path_parts = excluded_path_parts or DEFAULT_EXCLUDED_PATH_PARTS
        self.skill_md_patterns = skill_md_patterns or list(DEFAULT_SKILL_MD_PATTERNS)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": (
                "SkillLens github-skill scraper "
                "(+https://github.com/yourusername/skilllens)"
            ),
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _api_get_json(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        path: str,
        attempts: int = 4,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                await limiter.acquire()
                response = await client.get(
                    f"{GITHUB_API_BASE}{path}", timeout=self.timeout_seconds
                )
                if response.status_code == 404:
                    raise ScraperError(f"GitHub API not found: {path}")
                if response.status_code >= 500:
                    raise ScraperError(
                        f"GitHub API server error {response.status_code} for {path}"
                    )
                if response.status_code in {403, 429}:
                    raise ScraperError(
                        f"Rate limit or forbidden {response.status_code} for {path}"
                    )
                if response.status_code >= 400:
                    body = response.text[:200]
                    raise ScraperError(
                        f"GitHub API HTTP {response.status_code} for {path}: {body}"
                    )
                return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == attempts:
                    break
                await asyncio.sleep(min(10.0, 0.8 * (2 ** (attempt - 1))))
        raise ScraperError(f"Failed API request {path}: {last_error}") from last_error

    async def _get_repo_default_branch(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        owner: str,
        repo: str,
    ) -> str:
        payload = await self._api_get_json(client, limiter, f"/repos/{owner}/{repo}")
        branch = payload.get("default_branch")
        if not isinstance(branch, str) or not branch:
            raise ScraperError(f"Missing default_branch for {owner}/{repo}")
        return branch

    async def _get_repo_tree(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        owner: str,
        repo: str,
        ref: str,
    ) -> list[dict[str, Any]]:
        payload = await self._api_get_json(
            client,
            limiter,
            f"/repos/{owner}/{repo}/git/trees/{ref}?recursive=1",
        )
        tree = payload.get("tree")
        if not isinstance(tree, list):
            raise ScraperError(f"Invalid tree payload for {owner}/{repo}@{ref}")
        return tree

    async def _get_file_from_contents_api(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> GitHubFile:
        payload = await self._api_get_json(
            client,
            limiter,
            f"/repos/{owner}/{repo}/contents/{path}?ref={ref}",
        )
        if payload.get("type") != "file":
            raise ScraperError(f"Path is not file: {owner}/{repo}:{path}")

        raw_size = payload.get("size")
        if not isinstance(raw_size, int):
            raise ScraperError(f"Missing size for file {path}")
        if should_skip_by_size(raw_size, self.max_file_size_bytes):
            raise ScraperError(f"File exceeds size cap ({raw_size} bytes): {path}")

        encoded = payload.get("content", "")
        encoding = payload.get("encoding")
        if encoding != "base64" or not isinstance(encoded, str):
            raise ScraperError(f"Unsupported encoding for {path}: {encoding}")

        try:
            decoded_bytes = base64.b64decode(encoded, validate=False)
        except Exception as exc:  # noqa: BLE001
            raise ScraperError(f"Failed decoding base64 file {path}: {exc}") from exc
        if is_probably_binary(path, decoded_bytes):
            raise ScraperError(f"Binary file skipped: {path}")

        try:
            text = decoded_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = decoded_bytes.decode("utf-8", errors="replace")

        fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        sha = str(payload.get("sha") or "")
        download_url = str(payload.get("download_url") or "")
        if not download_url:
            download_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"

        return GitHubFile(
            path=path,
            sha=sha,
            size=raw_size,
            download_url=download_url,
            content=text,
            content_hash=sha256_text(text),
            fetched_at=fetched_at,
        )

    def _repo_base_dir(self, owner: str, repo: str, skill_slug: str) -> Path:
        return (
            self.outdir
            / "repos"
            / f"{sanitize_segment(owner)}__{sanitize_segment(repo)}"
            / "skills"
            / sanitize_segment(skill_slug)
        )

    def _record_path(self, owner: str, repo: str, skill_slug: str) -> Path:
        return self._repo_base_dir(owner, repo, skill_slug) / "skill_repo_record.json"

    def _skill_file_path(self, owner: str, repo: str, skill_slug: str) -> Path:
        return self._repo_base_dir(owner, repo, skill_slug) / "SKILL.md"

    def _files_dir(self, owner: str, repo: str, skill_slug: str) -> Path:
        return self._repo_base_dir(owner, repo, skill_slug) / "files"

    def _should_exclude_path(self, path: str) -> bool:
        parts = {part.lower() for part in Path(path).parts}
        excluded = {part.lower() for part in self.excluded_path_parts}
        return bool(parts & excluded)

    def _collect_heuristic_paths(
        self,
        tree_entries: list[dict[str, Any]],
        skill_md_path: str,
    ) -> list[str]:
        folder = str(Path(skill_md_path).parent).replace("\\", "/")
        if folder == ".":
            folder = ""

        result: list[str] = []
        for entry in tree_entries:
            if entry.get("type") != "blob":
                continue
            path = str(entry.get("path") or "")
            if not path:
                continue
            if folder and not path.startswith(f"{folder}/"):
                continue
            if path == skill_md_path:
                continue
            if self._should_exclude_path(path):
                continue
            size = int(entry.get("size") or 0)
            if should_skip_by_size(size, self.max_file_size_bytes):
                continue
            if should_skip_by_extension(path, self.allowed_extensions):
                continue
            result.append(path)
        return sorted(set(result))

    async def _process_skill(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        repo_counts: dict[tuple[str, str], int],
        record: dict[str, str],
        state_skills: dict[str, Any],
        state_lock: asyncio.Lock,
        dry_run: bool,
        print_jsonl: bool,
    ) -> tuple[str, dict[str, Any]]:
        owner = record["owner"]
        repo = record["repo"]
        skill_slug = record["skill_slug"]
        repository_url = record["repository_url"]
        state_key = skill_state_key(owner, repo, skill_slug)
        errors: list[str] = []

        try:
            default_branch = await self._get_repo_default_branch(client, limiter, owner, repo)
            tree_entries = await self._get_repo_tree(client, limiter, owner, repo, default_branch)
            tree_paths = {
                str(entry.get("path") or "")
                for entry in tree_entries
                if entry.get("type") == "blob" and entry.get("path")
            }
            skill_md_path = locate_skill_md_path(
                tree_paths=tree_paths,
                skill_slug=skill_slug,
                repo_skill_count=repo_counts.get((owner, repo), 1),
                patterns=self.skill_md_patterns,
            )
            if not skill_md_path:
                raise ScraperError(f"Could not locate SKILL.md for slug={skill_slug}")

            skill_file = await self._get_file_from_contents_api(
                client,
                limiter,
                owner,
                repo,
                skill_md_path,
                default_branch,
            )
            extracted_paths = extract_paths_from_skill_md(
                skill_file.content,
                owner=owner,
                repo=repo,
                skill_md_path=skill_md_path,
                allowed_extensions=self.allowed_extensions,
            )

            file_candidates = [path for path in extracted_paths if path in tree_paths]
            if not file_candidates:
                file_candidates = self._collect_heuristic_paths(tree_entries, skill_md_path)

            file_shas: dict[str, str] = {}
            for entry in tree_entries:
                if entry.get("type") != "blob":
                    continue
                path = str(entry.get("path") or "")
                if path in file_candidates:
                    file_shas[path] = str(entry.get("sha") or "")

            async with state_lock:
                previous = state_skills.get(state_key)

            event = decide_update_event(previous, skill_file.sha, file_shas)
            prev_files = previous.get("files", {}) if isinstance(previous, dict) else {}

            referenced_files: list[dict[str, Any]] = []
            for path in sorted(file_candidates):
                curr_sha = file_shas.get(path, "")
                prev_meta = prev_files.get(path, {})
                prev_sha = prev_meta.get("sha")
                needs_fetch = event in {"NEW", "UPDATED"} or prev_sha != curr_sha

                if not needs_fetch:
                    referenced_files.append(
                        {
                            "path": path,
                            "sha": curr_sha,
                            "size": prev_meta.get("size", 0),
                            "download_url": prev_meta.get("download_url", ""),
                            "content_hash": prev_meta.get("hash", ""),
                            "fetched_at": prev_meta.get("fetched_at", ""),
                        }
                    )
                    continue

                try:
                    file_obj = await self._get_file_from_contents_api(
                        client,
                        limiter,
                        owner,
                        repo,
                        path,
                        default_branch,
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Failed file {path}: {exc}")
                    if prev_sha == curr_sha and prev_meta:
                        referenced_files.append(
                            {
                                "path": path,
                                "sha": curr_sha,
                                "size": prev_meta.get("size", 0),
                                "download_url": prev_meta.get("download_url", ""),
                                "content_hash": prev_meta.get("hash", ""),
                                "fetched_at": prev_meta.get("fetched_at", ""),
                            }
                        )
                    continue

                referenced_files.append(
                    {
                        "path": file_obj.path,
                        "sha": file_obj.sha,
                        "size": file_obj.size,
                        "download_url": file_obj.download_url,
                        "content_hash": file_obj.content_hash,
                        "fetched_at": file_obj.fetched_at,
                    }
                )
                if not dry_run:
                    out_path = safe_output_path(self._files_dir(owner, repo, skill_slug), file_obj.path)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(file_obj.content, encoding="utf-8")

            now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            record_json = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"github://{owner}/{repo}/{skill_slug}")),
                "source": "github",
                "owner": owner,
                "repo": repo,
                "skill_slug": skill_slug,
                "repository_url": repository_url,
                "default_branch": default_branch,
                "skill_md_path": skill_md_path,
                "skill_md_content": skill_file.content,
                "skill_md_sha": skill_file.sha,
                "skill_md_hash": skill_file.content_hash,
                "referenced_files": referenced_files,
                "extracted_paths_from_skill_md": extracted_paths,
                "fetched_at": now,
                "last_seen_at": now,
                "parse_version": PARSE_VERSION,
                "errors": errors,
            }

            if not dry_run and event in {"NEW", "UPDATED"}:
                skill_path = self._skill_file_path(owner, repo, skill_slug)
                skill_path.parent.mkdir(parents=True, exist_ok=True)
                skill_path.write_text(skill_file.content, encoding="utf-8")

            if not dry_run and event in {"NEW", "UPDATED", "UPDATED_FILE"}:
                record_path = self._record_path(owner, repo, skill_slug)
                record_path.parent.mkdir(parents=True, exist_ok=True)
                record_path.write_text(
                    json.dumps(record_json, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

            async with state_lock:
                state_skills[state_key] = {
                    "skill_md_sha": skill_file.sha,
                    "skill_md_hash": skill_file.content_hash,
                    "files": {
                        entry["path"]: {
                            "sha": entry["sha"],
                            "hash": entry["content_hash"],
                            "size": entry["size"],
                            "download_url": entry.get("download_url", ""),
                            "fetched_at": entry["fetched_at"],
                        }
                        for entry in referenced_files
                    },
                    "last_fetched_at": now,
                    "last_seen_at": now,
                    "default_branch": default_branch,
                    "skill_md_path": skill_md_path,
                }

            payload = {
                "event": event,
                "owner": owner,
                "repo": repo,
                "skill_slug": skill_slug,
                "details": {
                    "skill_md_path": skill_md_path,
                    "referenced_file_count": len(referenced_files),
                    "errors": errors,
                },
            }
            if print_jsonl:
                print(json.dumps(payload, ensure_ascii=False))
            return event, payload
        except Exception as exc:  # noqa: BLE001
            now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            payload = {
                "event": "FAILED",
                "owner": owner,
                "repo": repo,
                "skill_slug": skill_slug,
                "details": {"error": str(exc), "fetched_at": now},
            }
            if print_jsonl:
                print(json.dumps(payload, ensure_ascii=False))
            return "FAILED", payload

    async def scrape(
        self,
        records: list[dict[str, str]],
        dry_run: bool = False,
        print_jsonl: bool = True,
    ) -> dict[str, Any]:
        """Run scraper over provided skill records."""
        timeout = httpx.Timeout(self.timeout_seconds)
        limiter = AsyncRateLimiter(self.rate_limit)
        semaphore = asyncio.Semaphore(self.concurrency)

        repo_counts: dict[tuple[str, str], int] = {}
        for record in records:
            key = (record["owner"], record["repo"])
            repo_counts[key] = repo_counts.get(key, 0) + 1

        state = load_state(self.state_path)
        state_skills = state.setdefault("skills", {})
        state_lock = asyncio.Lock()

        summary = {
            "total": len(records),
            "new": 0,
            "updated": 0,
            "updated_file": 0,
            "unchanged": 0,
            "failed": 0,
        }

        async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:

            async def run_one(record: dict[str, str]) -> tuple[str, dict[str, Any]]:
                async with semaphore:
                    return await self._process_skill(
                        client=client,
                        limiter=limiter,
                        repo_counts=repo_counts,
                        record=record,
                        state_skills=state_skills,
                        state_lock=state_lock,
                        dry_run=dry_run,
                        print_jsonl=print_jsonl,
                    )

            tasks = [asyncio.create_task(run_one(record)) for record in records]
            for coro in asyncio.as_completed(tasks):
                event, _payload = await coro
                if event == "NEW":
                    summary["new"] += 1
                elif event == "UPDATED":
                    summary["updated"] += 1
                elif event == "UPDATED_FILE":
                    summary["updated_file"] += 1
                elif event == "UNCHANGED":
                    summary["unchanged"] += 1
                else:
                    summary["failed"] += 1

        if not dry_run:
            save_state(self.state_path, state)

        return summary


def sample_records(
    records: list[dict[str, str]],
    include_all: bool,
    count: int | None,
    seed: int | None,
) -> list[dict[str, str]]:
    """Select all records or a deterministic random subset."""
    if include_all:
        return records
    if count is None or count <= 0:
        raise ValueError("count must be provided and > 0 when include_all=False")
    if count >= len(records):
        return records
    rng = random.Random(seed)
    return rng.sample(records, count)
