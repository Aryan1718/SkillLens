"""Supabase-backed cache and skills data helpers."""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from datetime import datetime, timezone
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
        # Fallback for local `supabase/` folder shadowing the installed package.
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
            return None, fallback_exc
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


def get_supabase() -> Client:
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


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    return None


def is_cache_valid(cache_until: datetime | None) -> bool:
    """Check whether a cache timestamp has not expired."""
    if cache_until is None:
        return False
    now = datetime.now(timezone.utc)
    return cache_until >= now


async def get_cached_analysis(content_hash: str) -> dict[str, Any] | None:
    """Return the most recent valid cached analysis row for a content hash."""

    def _query() -> list[dict[str, Any]]:
        response = (
            get_supabase()
            .table("analyses")
            .select("*")
            .eq("content_hash", content_hash)
            .order("analyzed_at", desc=True)
            .limit(10)
            .execute()
        )
        return response.data or []

    rows = await asyncio.to_thread(_query)
    for row in rows:
        if is_cache_valid(_parse_ts(row.get("cache_until"))):
            return row
    return None


async def store_analysis(record: dict[str, Any]) -> dict[str, Any]:
    """Insert an analysis row and return the inserted record."""

    def _insert() -> dict[str, Any]:
        response = get_supabase().table("analyses").insert(record).execute()
        data = response.data or []
        return data[0] if data else {}

    return await asyncio.to_thread(_insert)


async def upsert_skill(record: dict[str, Any]) -> dict[str, Any]:
    """Upsert a skill row using canonical identity keys."""

    def _upsert() -> dict[str, Any]:
        response = (
            get_supabase()
            .table("skills")
            .upsert(record, on_conflict="source,owner,repo,skill_slug")
            .execute()
        )
        data = response.data or []
        return data[0] if data else {}

    return await asyncio.to_thread(_upsert)


async def list_skills(limit: int = 50) -> list[dict[str, Any]]:
    """List skills for UI display, ordered by installs then recency."""

    def _list() -> list[dict[str, Any]]:
        response = (
            get_supabase()
            .table("skills")
            .select(
                "id,source,owner,repo,skill_slug,page_url,repository_url,install_command,"
                "skill_md_hash,weekly_installs,installed_on,last_seen_at,parse_version"
            )
            .order("weekly_installs", desc=True)
            .order("last_seen_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    return await asyncio.to_thread(_list)
