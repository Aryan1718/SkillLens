"""Supabase Storage helpers for artifact uploads."""

from __future__ import annotations

from typing import Any

try:
    from server.core.db import get_supabase_client
except ModuleNotFoundError:
    from core.db import get_supabase_client


def upload_bytes(
    bucket: str,
    object_key: str,
    content_bytes: bytes,
    content_type: str,
) -> dict[str, Any]:
    """Upload bytes to a Storage object path."""
    response = (
        get_supabase_client()
        .storage.from_(bucket)
        .upload(
            path=object_key,
            file=content_bytes,
            file_options={"content-type": content_type, "upsert": "false"},
        )
    )
    return response or {}


def object_exists(bucket: str, object_key: str) -> bool:
    """Return true when an object key already exists."""
    prefix, _, name = object_key.rpartition("/")
    list_path = prefix or ""
    items = get_supabase_client().storage.from_(bucket).list(path=list_path)
    if not isinstance(items, list):
        return False
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return True
    return False


def download_text(bucket: str, object_key: str) -> str | None:
    """Download object bytes and decode as UTF-8 text; return None for binary."""
    blob = get_supabase_client().storage.from_(bucket).download(object_key)
    if blob is None:
        return None
    if isinstance(blob, str):
        return blob
    if not isinstance(blob, (bytes, bytearray)):
        return None
    raw = bytes(blob)
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
