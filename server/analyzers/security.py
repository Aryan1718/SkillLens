"""Deterministic security analyzer for skill artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal


Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Confidence = Literal["low", "medium", "high"]
Category = Literal["exec", "filesystem", "network", "secrets", "deps", "prompt_injection"]

SEVERITY_WEIGHTS: dict[Severity, int] = {
    "CRITICAL": 100,
    "HIGH": 25,
    "MEDIUM": 5,
    "LOW": 1,
}


@dataclass(frozen=True)
class ScannedFile:
    path: str
    text: str


@dataclass(frozen=True)
class Finding:
    id: str
    category: Category
    severity: Severity
    title: str
    evidence: str
    file_path: str
    line_start: int | None
    line_end: int | None
    confidence: Confidence


@dataclass(frozen=True)
class SecurityScanResult:
    findings: list[Finding]
    risk_score: int
    trust_badge: str
    capabilities: dict[str, bool]


@dataclass(frozen=True)
class _Rule:
    rule_id: str
    category: Category
    severity: Severity
    title: str
    confidence: Confidence
    pattern: re.Pattern[str]
    file_extensions: tuple[str, ...] | None = None
    file_name_regex: re.Pattern[str] | None = None


_RULES: tuple[_Rule, ...] = (
    _Rule(
        "SEC_PY_EVAL_001",
        "exec",
        "CRITICAL",
        "Python dynamic code execution detected (eval/exec).",
        "high",
        re.compile(r"\b(eval|exec)\s*\(", re.IGNORECASE),
        file_extensions=(".py",),
    ),
    _Rule(
        "SEC_PY_SHELL_TRUE_001",
        "exec",
        "HIGH",
        "subprocess call with shell=True detected.",
        "high",
        re.compile(
            r"subprocess\.(run|Popen|call|check_output|check_call)\s*\([^)]*shell\s*=\s*True",
            re.IGNORECASE,
        ),
        file_extensions=(".py",),
    ),
    _Rule(
        "SEC_PY_OS_SYSTEM_001",
        "exec",
        "HIGH",
        "Shell execution via os.system/popen detected.",
        "high",
        re.compile(r"\b(os\.system|popen)\s*\(", re.IGNORECASE),
        file_extensions=(".py", ".sh", ".bash", ".zsh"),
    ),
    _Rule(
        "SEC_JS_EVAL_001",
        "exec",
        "CRITICAL",
        "JavaScript dynamic code execution detected (eval/new Function).",
        "high",
        re.compile(r"\b(eval\s*\(|new\s+Function\s*\()", re.IGNORECASE),
        file_extensions=(".js", ".ts", ".mjs", ".cjs"),
    ),
    _Rule(
        "SEC_JS_CHILD_PROCESS_001",
        "exec",
        "HIGH",
        "child_process command execution detected.",
        "high",
        re.compile(r"child_process\.(exec|spawn)\s*\(", re.IGNORECASE),
        file_extensions=(".js", ".ts", ".mjs", ".cjs"),
    ),
    _Rule(
        "SEC_SH_PIPE_EXEC_001",
        "exec",
        "CRITICAL",
        "Remote script piping into shell detected (curl|sh or wget|bash).",
        "high",
        re.compile(r"(curl\s+[^|]+?\|\s*(sh|bash))|(wget\s+[^|]+?\|\s*(sh|bash))", re.IGNORECASE),
        file_extensions=(".sh", ".bash", ".zsh", ".md", ".txt", ".yaml", ".yml"),
    ),
    _Rule(
        "SEC_FS_RM_RF_001",
        "filesystem",
        "CRITICAL",
        "Destructive recursive deletion detected (rm -rf / rmtree).",
        "high",
        re.compile(r"(rm\s+-rf\b|shutil\.rmtree\s*\()", re.IGNORECASE),
    ),
    _Rule(
        "SEC_FS_SENSITIVE_WRITE_001",
        "filesystem",
        "HIGH",
        "Write or modification of sensitive system path detected.",
        "medium",
        re.compile(r"(~\/\.ssh|\/etc\/|\/usr\/|\/var\/)", re.IGNORECASE),
    ),
    _Rule(
        "SEC_FS_PATH_TRAVERSAL_001",
        "filesystem",
        "MEDIUM",
        "Potential path traversal pattern with user-controlled path.",
        "medium",
        re.compile(r"\.\.\/.*(user|input|param|request|query)", re.IGNORECASE),
    ),
    _Rule(
        "SEC_NET_USER_URL_001",
        "network",
        "MEDIUM",
        "Potential SSRF: outbound request built from user-controlled URL.",
        "medium",
        re.compile(
            r"(requests\.(get|post|put|delete)\s*\(\s*(user_?url|url_from_user|input_url|request\.)|"
            r"fetch\s*\(\s*(user_?url|urlFromUser|inputUrl|req\.))",
            re.IGNORECASE,
        ),
    ),
    _Rule(
        "SEC_NET_RAW_SOCKET_001",
        "network",
        "HIGH",
        "Raw socket usage detected.",
        "medium",
        re.compile(r"(socket\.socket\s*\(|new\s+Socket\s*\()", re.IGNORECASE),
    ),
    _Rule(
        "SEC_NET_METADATA_001",
        "network",
        "HIGH",
        "Cloud metadata endpoint access detected.",
        "high",
        re.compile(r"169\.254\.169\.254", re.IGNORECASE),
    ),
    _Rule(
        "SEC_SECRET_ENV_EXFIL_001",
        "secrets",
        "HIGH",
        "Environment secret read and outbound request pattern detected.",
        "medium",
        re.compile(
            r"((os\.environ|getenv|process\.env).*(requests\.|fetch\s*\())|"
            r"((requests\.|fetch\s*\().*(os\.environ|getenv|process\.env))",
            re.IGNORECASE,
        ),
    ),
    _Rule(
        "SEC_SECRET_TOKEN_LOG_001",
        "secrets",
        "MEDIUM",
        "Potential secret logging or Authorization header exposure.",
        "medium",
        re.compile(r"(Authorization|api[_-]?key|token).*(print|console\.log)|"
                   r"(print|console\.log).*(Authorization|api[_-]?key|token)", re.IGNORECASE),
    ),
    _Rule(
        "SEC_DEP_POSTINSTALL_001",
        "deps",
        "HIGH",
        "NPM postinstall script detected.",
        "high",
        re.compile(r'"postinstall"\s*:', re.IGNORECASE),
        file_name_regex=re.compile(r"package\.json$", re.IGNORECASE),
    ),
    _Rule(
        "SEC_DEP_NPM_GIT_HTTP_001",
        "deps",
        "MEDIUM",
        "Git or HTTP dependency source detected in package.json.",
        "medium",
        re.compile(r"(git\+https?:\/\/|https?:\/\/.*\.tgz|github:)", re.IGNORECASE),
        file_name_regex=re.compile(r"package\.json$", re.IGNORECASE),
    ),
    _Rule(
        "SEC_DEP_PY_GIT_URL_001",
        "deps",
        "LOW",
        "requirements.txt contains git-based dependency.",
        "medium",
        re.compile(r"git\+https?:\/\/", re.IGNORECASE),
        file_name_regex=re.compile(r"requirements.*\.txt$", re.IGNORECASE),
    ),
    _Rule(
        "SEC_SKILL_PROMPT_INJ_001",
        "prompt_injection",
        "HIGH",
        "Prompt injection style unsafe instruction in SKILL.md.",
        "medium",
        re.compile(
            r"(ignore\s+previous|exfiltrate|send\s+secrets|disable\s+safeguards)",
            re.IGNORECASE,
        ),
        file_name_regex=re.compile(r"SKILL\.md$", re.IGNORECASE),
    ),
)


def _trust_badge(risk_score: int) -> str:
    if risk_score <= 4:
        return "Verified Safe"
    if risk_score <= 19:
        return "Generally Safe"
    if risk_score <= 49:
        return "Review Recommended"
    if risk_score <= 99:
        return "Use With Caution"
    return "Not Recommended"


def _evidence(text: str) -> str:
    one_line = " ".join(text.strip().split())
    return one_line[:240]


def _line_number(text: str, offset: int) -> int | None:
    if offset < 0:
        return None
    return text.count("\n", 0, offset) + 1


def _is_rule_applicable(rule: _Rule, path: str) -> bool:
    lowered = path.lower()
    if rule.file_extensions and not lowered.endswith(rule.file_extensions):
        return False
    if rule.file_name_regex and not rule.file_name_regex.search(path):
        return False
    return True


def _finding_id(rule_id: str, file_path: str, line_start: int | None, evidence: str) -> str:
    stable = f"{rule_id}:{file_path}:{line_start}:{evidence}".encode("utf-8", "ignore")
    digest = hashlib.sha1(stable).hexdigest()[:8]  # noqa: S324 - deterministic identifier only
    return f"{rule_id}_{digest}"


def _extra_dep_checks(file: ScannedFile, findings: list[Finding]) -> None:
    path_lower = file.path.lower()
    if path_lower.endswith("package.json"):
        try:
            payload = json.loads(file.text)
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            deps: dict[str, str] = {}
            for block in ("dependencies", "devDependencies", "optionalDependencies"):
                dep_block = payload.get(block)
                if isinstance(dep_block, dict):
                    deps.update({str(k): str(v) for k, v in dep_block.items()})
            for dep_name, dep_ver in deps.items():
                if dep_ver in {"*", "latest"} or dep_ver.strip().startswith("^"):
                    evidence = f'"{dep_name}": "{dep_ver}"'
                    findings.append(
                        Finding(
                            id=_finding_id("SEC_DEP_UNPINNED_NPM_001", file.path, None, evidence),
                            category="deps",
                            severity="LOW",
                            title="Unpinned NPM dependency version detected.",
                            evidence=_evidence(evidence),
                            file_path=file.path,
                            line_start=None,
                            line_end=None,
                            confidence="medium",
                        )
                    )
    if "requirements" in path_lower and path_lower.endswith(".txt"):
        for idx, line in enumerate(file.text.splitlines(), start=1):
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue
            if "==" not in clean and not clean.startswith(("-e ", "git+")):
                evidence = clean
                findings.append(
                    Finding(
                        id=_finding_id("SEC_DEP_UNPINNED_PY_001", file.path, idx, evidence),
                        category="deps",
                        severity="LOW",
                        title="Unpinned Python dependency detected.",
                        evidence=_evidence(evidence),
                        file_path=file.path,
                        line_start=idx,
                        line_end=idx,
                        confidence="low",
                    )
                )


def scan_security(files: list[ScannedFile]) -> SecurityScanResult:
    """Run deterministic security checks over decoded text artifacts."""
    findings: list[Finding] = []
    capabilities = {
        "network": False,
        "file_write": False,
        "file_delete": False,
        "shell_exec": False,
        "reads_env": False,
        "db_access": False,
    }

    for file in files:
        if not file.text:
            continue

        text_lower = file.text.lower()
        if re.search(r"\b(requests\.|fetch\s*\(|httpx\.|urllib\.)", text_lower):
            capabilities["network"] = True
        if re.search(r"\b(open\s*\(.+['\"]w|write_text\s*\(|fs\.writefile|tee\s+)", text_lower):
            capabilities["file_write"] = True
        if re.search(r"\b(rm\s+-rf|rmtree\s*\(|unlink\s*\()", text_lower):
            capabilities["file_delete"] = True
        if re.search(r"\b(subprocess\.|os\.system|child_process\.)", text_lower):
            capabilities["shell_exec"] = True
        if re.search(r"\b(os\.environ|getenv|process\.env)\b", text_lower):
            capabilities["reads_env"] = True
        if re.search(r"\b(select\s+.+\s+from|insert\s+into|sqlalchemy|psycopg|sqlite3|mongodb)\b", text_lower):
            capabilities["db_access"] = True

        for rule in _RULES:
            if not _is_rule_applicable(rule, file.path):
                continue
            for match in rule.pattern.finditer(file.text):
                snippet_start = max(0, match.start() - 50)
                snippet_end = min(len(file.text), match.end() + 120)
                snippet = file.text[snippet_start:snippet_end]
                line = _line_number(file.text, match.start())
                findings.append(
                    Finding(
                        id=_finding_id(rule.rule_id, file.path, line, snippet),
                        category=rule.category,
                        severity=rule.severity,
                        title=rule.title,
                        evidence=_evidence(snippet),
                        file_path=file.path,
                        line_start=line,
                        line_end=line,
                        confidence=rule.confidence,
                    )
                )

        _extra_dep_checks(file, findings)

    risk_score = sum(SEVERITY_WEIGHTS[item.severity] for item in findings)
    risk_score = min(risk_score, 200)
    badge = _trust_badge(risk_score)
    return SecurityScanResult(
        findings=findings,
        risk_score=risk_score,
        trust_badge=badge,
        capabilities=capabilities,
    )
