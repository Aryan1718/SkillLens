"""Background job runner for artifact analysis jobs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from server.analyzers.security import Finding, ScannedFile, scan_security
    from server.analyzers.security_llm import (
        ContextSnippet,
        should_validate_with_openai,
        validate_findings_with_openai,
    )
    from server.core.db import (
        db_claim_next_job,
        db_ensure_skill_analysis_for_artifact,
        db_enqueue_analyze_jobs_from_existing_artifacts,
        db_finish_job,
        db_get_skill_artifact,
        db_get_skill_artifact_files,
        db_get_skill_text_content,
        db_update_skill_analysis_security,
        db_update_skill_analysis_status,
    )
    from server.core.storage import download_text
except ModuleNotFoundError:
    from analyzers.security import Finding, ScannedFile, scan_security
    from analyzers.security_llm import (
        ContextSnippet,
        should_validate_with_openai,
        validate_findings_with_openai,
    )
    from core.db import (
        db_claim_next_job,
        db_ensure_skill_analysis_for_artifact,
        db_enqueue_analyze_jobs_from_existing_artifacts,
        db_finish_job,
        db_get_skill_artifact,
        db_get_skill_artifact_files,
        db_get_skill_text_content,
        db_update_skill_analysis_security,
        db_update_skill_analysis_status,
    )
    from core.storage import download_text


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "category": finding.category,
        "severity": finding.severity,
        "title": finding.title,
        "evidence": finding.evidence,
        "file_path": finding.file_path,
        "line_start": finding.line_start,
        "line_end": finding.line_end,
        "confidence": finding.confidence,
    }


def _prepare_scanned_files(
    bucket: str,
    files_manifest: list[dict[str, Any]],
    skill_text: str,
) -> list[ScannedFile]:
    files: list[ScannedFile] = []
    if skill_text.strip():
        files.append(ScannedFile(path="SKILL.md", text=skill_text))
    for item in files_manifest:
        object_key = item.get("object_key")
        path = item.get("path") or object_key
        if not isinstance(object_key, str) or not isinstance(path, str):
            continue
        text = download_text(bucket, object_key)
        if text is None:
            continue
        files.append(ScannedFile(path=path, text=text))
    return files


def _context_snippets(scanned_files: list[ScannedFile], findings: list[Finding]) -> list[ContextSnippet]:
    findings_by_file: dict[str, list[Finding]] = {}
    for finding in findings:
        findings_by_file.setdefault(finding.file_path, []).append(finding)

    snippets: list[ContextSnippet] = []
    for item in scanned_files:
        related = findings_by_file.get(item.path)
        if not related:
            continue
        excerpt = item.text[:1200]
        snippets.append(ContextSnippet(file_path=item.path, snippet=excerpt))
        if len(snippets) >= 20:
            break
    return snippets


def _process_analyze_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    artifact_id = job.get("artifact_id")
    if not artifact_id:
        raise ValueError(f"Analyze job {job_id} is missing artifact_id.")

    artifact_row = db_get_skill_artifact(str(artifact_id))
    if not artifact_row:
        raise ValueError(f"Artifact {artifact_id} not found.")

    files_manifest = db_get_skill_artifact_files(str(artifact_id))
    bucket_name = artifact_row.get("bucket_name") or "skill-artifacts"
    skill_id = artifact_row.get("skill_id")
    skill_text = db_get_skill_text_content(str(skill_id)) if isinstance(skill_id, str) else ""
    scanned_files = _prepare_scanned_files(bucket_name, files_manifest, skill_text)
    scan_result = scan_security(scanned_files)

    findings = scan_result.findings
    llm_used = False
    llm_model: str | None = None
    validated_findings: list[dict[str, Any]] = []
    security_summary: str | None = None
    if should_validate_with_openai(findings, scan_result.risk_score):
        llm_used = True
        has_uncertain_critical = any(
            item.severity == "CRITICAL" and item.confidence in {"low", "medium"} for item in findings
        )
        llm_model = "gpt-5.1" if has_uncertain_critical else "o4-mini"
        validation = validate_findings_with_openai(findings, _context_snippets(scanned_files, findings))
        validated_findings = [item.model_dump() for item in validation.validated_findings]
        security_summary = validation.security_summary

    high_or_critical = [
        item for item in findings if item.severity in {"HIGH", "CRITICAL"}
    ]
    if security_summary:
        user_summary = security_summary
    elif not findings:
        user_summary = "No risky execution or exfiltration patterns were detected in scanned text artifacts."
    elif not high_or_critical:
        user_summary = (
            "Only low-to-medium risk patterns were detected. Review findings, but no immediate high-risk behavior "
            "was found in this scan."
        )
    else:
        user_summary = (
            f"{len(high_or_critical)} high-risk pattern(s) detected. Review command execution, file deletion, "
            "or network-related findings before installing."
        )

    top_concerns = [item.title for item in high_or_critical[:3]]
    if not top_concerns and findings:
        top_concerns = [item.title for item in findings[:3]]

    recommended_actions: list[str] = []
    for item in validated_findings[:4]:
        mitigation = item.get("mitigation")
        if isinstance(mitigation, list):
            for bullet in mitigation:
                if isinstance(bullet, str) and bullet.strip():
                    recommended_actions.append(bullet.strip())
    if not recommended_actions:
        recommended_actions = [
            "Inspect shell and subprocess calls for user-controlled inputs.",
            "Review network requests and sensitive file operations before use.",
            "Avoid installing skills that require broad system access unless necessary.",
        ]
    recommended_actions = recommended_actions[:4]

    capabilities = scan_result.capabilities
    safety_checks = [
        {
            "key": "shell_exec",
            "safe": not capabilities.get("shell_exec", False),
            "safe_message": "No shell execution behavior detected.",
            "risk_message": "Shell execution behavior detected; review commands and input handling.",
        },
        {
            "key": "db_access",
            "safe": not capabilities.get("db_access", False),
            "safe_message": "No database access patterns detected.",
            "risk_message": "Database access patterns detected; verify query safety and permissions.",
        },
        {
            "key": "file_delete",
            "safe": not capabilities.get("file_delete", False),
            "safe_message": "No destructive file deletion behavior detected.",
            "risk_message": "Potential file deletion behavior detected; review scope and safeguards.",
        },
        {
            "key": "network",
            "safe": not capabilities.get("network", False),
            "safe_message": "No outbound network behavior detected.",
            "risk_message": "Outbound network behavior detected; verify destination allowlist.",
        },
        {
            "key": "reads_env",
            "safe": not capabilities.get("reads_env", False),
            "safe_message": "No environment variable reads detected.",
            "risk_message": "Environment variable reads detected; ensure secrets are not exposed.",
        },
    ]
    safety_statements = [
        check["safe_message"] if check["safe"] else check["risk_message"]
        for check in safety_checks
    ]

    analyzed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    overall_score = float(max(0, 100 - min(scan_result.risk_score, 100)))
    security_data = {
        "findings": [_finding_to_dict(item) for item in findings],
        "validated_findings": validated_findings,
        "security_summary": security_summary,
        "user_explanation": {
            "headline": scan_result.trust_badge,
            "summary": user_summary,
            "top_concerns": top_concerns,
            "recommended_actions": recommended_actions,
            "safety_checks": safety_checks,
            "safety_statements": safety_statements,
        },
        "risk_score": scan_result.risk_score,
        "trust_badge": scan_result.trust_badge,
        "capabilities": capabilities,
        "llm_used": llm_used,
        "llm_model": llm_model,
        "analyzed_at": analyzed_at,
    }

    analysis_id = None
    payload = job.get("payload")
    if isinstance(payload, dict):
        payload_analysis_id = payload.get("analysis_id")
        if isinstance(payload_analysis_id, str) and payload_analysis_id:
            analysis_id = payload_analysis_id
    if analysis_id is None:
        ensured = db_ensure_skill_analysis_for_artifact(artifact_row)
        analysis_id = ensured.get("id")
    if not analysis_id:
        raise ValueError(f"Unable to resolve analysis row for artifact {artifact_id}.")

    db_update_skill_analysis_security(
        str(analysis_id),
        security_data,
        trust_badge=scan_result.trust_badge,
        overall_score=overall_score,
    )
    db_update_skill_analysis_status(str(analysis_id), "succeeded")
    db_finish_job(job_id, "succeeded")


def run_once() -> bool:
    """Process one queued analyze job. Returns true when a job was processed."""
    job = db_claim_next_job("analyze")
    if not job:
        return False
    job_id = str(job["id"])
    try:
        _process_analyze_job(job)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)[:1000]
        payload = job.get("payload")
        if isinstance(payload, dict):
            analysis_id = payload.get("analysis_id")
            if isinstance(analysis_id, str) and analysis_id:
                db_update_skill_analysis_status(analysis_id, "failed", error_message=error)
        db_finish_job(job_id, "failed", error=error)
        raise
    return True


def _enqueue_analyze_jobs(
    limit: int,
    offset: int,
    recent_only: bool,
    recent_days: int,
    fail_on_error: bool,
) -> None:
    """Populate artifact and analyze jobs via existing scraping pipeline."""
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "scrape_github_skill_repo.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Missing enqueue script: {script_path}")

    cmd = [
        sys.executable,
        str(script_path),
        "--limit",
        str(limit),
        "--offset",
        str(offset),
    ]
    if recent_only:
        cmd.extend(["--recent-only", "--recent-days", str(recent_days)])

    completed = subprocess.run(  # noqa: S603
        cmd,
        cwd=str(repo_root),
        check=False,
    )
    if completed.returncode != 0 and fail_on_error:
        raise RuntimeError(f"Failed to enqueue jobs (exit={completed.returncode})")
    if completed.returncode != 0 and not fail_on_error:
        print(
            f"enqueue_warning=1 enqueue_exit={completed.returncode} "
            "continuing_to_process_queued_jobs=1"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="SkillLens analysis job runner")
    parser.add_argument("--once", action="store_true", help="Process one queued analyze job")
    parser.add_argument(
        "--enqueue-first",
        action="store_true",
        help="Run artifact enqueue script before processing analyze jobs",
    )
    parser.add_argument("--enqueue-limit", type=int, default=50, help="Skill rows to enqueue")
    parser.add_argument("--enqueue-offset", type=int, default=0, help="Offset for enqueue query")
    parser.add_argument(
        "--enqueue-recent-only",
        action="store_true",
        help="Only enqueue recently seen skills",
    )
    parser.add_argument(
        "--enqueue-recent-days",
        type=int,
        default=7,
        help="Window for --enqueue-recent-only",
    )
    parser.add_argument(
        "--fail-on-enqueue-error",
        action="store_true",
        help="Stop immediately if enqueue step returns non-zero",
    )
    parser.add_argument(
        "--enqueue-from-db",
        action="store_true",
        help="Queue analyze jobs from existing skill_artifacts in DB (no GitHub fetch)",
    )
    parser.add_argument(
        "--db-enqueue-limit",
        type=int,
        default=200,
        help="Max artifacts to inspect for --enqueue-from-db",
    )
    args = parser.parse_args()

    if args.enqueue_first:
        _enqueue_analyze_jobs(
            limit=max(args.enqueue_limit, 1),
            offset=max(args.enqueue_offset, 0),
            recent_only=args.enqueue_recent_only,
            recent_days=max(args.enqueue_recent_days, 1),
            fail_on_error=args.fail_on_enqueue_error,
        )
    if args.enqueue_from_db:
        enqueued = db_enqueue_analyze_jobs_from_existing_artifacts(
            limit=max(args.db_enqueue_limit, 1)
        )
        print(f"db_enqueued={enqueued}")

    if args.once:
        processed = run_once()
        print("processed=1" if processed else "processed=0")
        return 0

    processed_any = False
    while run_once():
        processed_any = True
    print("processed=1" if processed_any else "processed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
