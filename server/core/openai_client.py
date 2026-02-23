"""Minimal OpenAI Responses API client wrapper."""

from __future__ import annotations

import os
from threading import Lock
from typing import Any

from openai import OpenAI

_client: OpenAI | None = None
_client_lock = Lock()


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY must be set for OpenAI validation.")
            _client = OpenAI(api_key=api_key)
    return _client


def create_response(
    model: str,
    input: list[dict[str, Any]],
    response_format: dict[str, Any],
    reasoning: str | None = None,
) -> dict[str, Any]:
    """Create one OpenAI Responses API call and return a serializable dict."""
    payload: dict[str, Any] = {
        "model": model,
        "input": input,
        "max_output_tokens": 700,
    }
    if reasoning:
        payload["reasoning"] = {"effort": reasoning}

    client = _get_client()
    try:
        response = client.responses.create(response_format=response_format, **payload)
    except TypeError:
        # Compatibility fallback for SDK versions expecting text.format.
        payload["text"] = {"format": response_format}
        response = client.responses.create(**payload)
    return response.model_dump()
