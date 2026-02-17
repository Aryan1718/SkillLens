"""Orchestrator and utility helpers."""

from __future__ import annotations

import hashlib


def compute_content_hash(skill_content: str) -> str:
    """Create a deterministic SHA-256 hash after normalizing line endings."""
    normalized = skill_content.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def run_analysis(_: dict) -> dict:
    return {"status": "stub"}
