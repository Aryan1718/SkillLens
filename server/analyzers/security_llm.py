"""Selective OpenAI validation for high-severity deterministic findings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

try:
    from server.analyzers.security import Finding, SEVERITY_WEIGHTS
    from server.core.openai_client import create_response
except ModuleNotFoundError:
    from analyzers.security import Finding, SEVERITY_WEIGHTS
    from core.openai_client import create_response


ValidatedSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


@dataclass(frozen=True)
class ContextSnippet:
    file_path: str
    snippet: str


class ValidatedFinding(BaseModel):
    finding_id: str
    is_true_positive: bool
    final_severity: ValidatedSeverity
    reason: str
    mitigation: list[str] = Field(default_factory=list)


class ValidatedSecurity(BaseModel):
    validated_findings: list[ValidatedFinding] = Field(default_factory=list)
    security_summary: str


VALIDATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "validated_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding_id": {"type": "string"},
                    "is_true_positive": {"type": "boolean"},
                    "final_severity": {
                        "type": "string",
                        "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    },
                    "reason": {"type": "string"},
                    "mitigation": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "finding_id",
                    "is_true_positive",
                    "final_severity",
                    "reason",
                    "mitigation",
                ],
                "additionalProperties": False,
            },
        },
        "security_summary": {"type": "string"},
    },
    "required": ["validated_findings", "security_summary"],
    "additionalProperties": False,
}


def should_validate_with_openai(findings: list[Finding], risk_score: int) -> bool:
    """Return true only when configured severity thresholds are exceeded."""
    critical_count = sum(1 for item in findings if item.severity == "CRITICAL")
    high_count = sum(1 for item in findings if item.severity == "HIGH")
    return critical_count > 0 or high_count >= 2 or risk_score >= 20


def _model_for_findings(findings: list[Finding]) -> tuple[str, str | None]:
    has_uncertain_critical = any(
        item.severity == "CRITICAL" and item.confidence in {"low", "medium"}
        for item in findings
    )
    if has_uncertain_critical:
        return "gpt-5.1", "low"
    return "o4-mini", None


def _find_response_json(payload: dict[str, Any]) -> dict[str, Any]:
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for entry in content:
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") in {"output_text", "text"}:
                    text_value = entry.get("text")
                    if isinstance(text_value, str):
                        return json.loads(text_value)
                if entry.get("type") == "output_json":
                    json_value = entry.get("json")
                    if isinstance(json_value, dict):
                        return json_value
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return json.loads(output_text)
    raise ValueError("OpenAI response did not contain parseable JSON output.")


def _summarize_findings(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for finding in findings:
        counts[finding.severity] += 1
    return counts


def validate_findings_with_openai(
    findings: list[Finding],
    context_snippets: list[ContextSnippet],
) -> ValidatedSecurity:
    """Validate existing findings with OpenAI; does not create new findings."""
    if not findings:
        return ValidatedSecurity(validated_findings=[], security_summary="No findings to validate.")

    model, reasoning = _model_for_findings(findings)
    findings_payload = [
        {
            "finding_id": item.id,
            "category": item.category,
            "severity": item.severity,
            "title": item.title,
            "confidence": item.confidence,
            "evidence": item.evidence,
            "file_path": item.file_path,
            "line_start": item.line_start,
            "line_end": item.line_end,
        }
        for item in findings
    ]
    context_payload = [
        {"file_path": snippet.file_path, "snippet": snippet.snippet[:600]}
        for snippet in context_snippets
    ]
    summary_counts = _summarize_findings(findings)
    risk_score = sum(SEVERITY_WEIGHTS[item.severity] for item in findings)

    system_instruction = (
        "You are a security validation assistant. Output only JSON that matches the schema exactly. "
        "Do not add new findings. Only validate items provided. "
        "If uncertain, mark is_true_positive=false and explain why."
    )
    user_input = {
        "task": "Validate deterministic findings and provide final severity and mitigations.",
        "risk_score": risk_score,
        "severity_counts": summary_counts,
        "findings": findings_payload,
        "context_snippets": context_payload,
        "constraints": {
            "reason_max_sentences": 2,
            "mitigation_max_items": 3,
            "security_summary_max_words": 60,
        },
    }
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "validated_security_output",
            "strict": True,
            "schema": VALIDATION_JSON_SCHEMA,
        },
    }

    response_payload = create_response(
        model=model,
        input=[
            {"role": "system", "content": [{"type": "text", "text": system_instruction}]},
            {"role": "user", "content": [{"type": "text", "text": json.dumps(user_input)}]},
        ],
        response_format=response_format,
        reasoning=reasoning,
    )
    validated_json = _find_response_json(response_payload)
    return ValidatedSecurity.model_validate(validated_json)
