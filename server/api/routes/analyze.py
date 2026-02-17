from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.cache import get_cached_analysis, store_analysis
from core.orchestrator import compute_content_hash

router = APIRouter(tags=["analyze"])


class AnalyzeRequest(BaseModel):
    source_type: Literal["github", "official", "upload"]
    github_url: str | None = None
    official_skill_name: str | None = None
    skill_content: str | None = None


class AnalyzeResponse(BaseModel):
    skill_name: str
    overall_score: float
    trust_badge: str
    security: dict = Field(default_factory=dict)
    quality: dict = Field(default_factory=dict)
    behavior: dict = Field(default_factory=dict)
    dependencies: dict = Field(default_factory=dict)
    analyzed_at: str


def _to_response_from_cache(row: dict) -> AnalyzeResponse:
    analyzed_at = row.get("analyzed_at")
    if isinstance(analyzed_at, str):
        analyzed = analyzed_at
    else:
        analyzed = datetime.now(timezone.utc).isoformat()

    github_url = row.get("github_url")
    fallback_name = "cached-skill"
    if isinstance(github_url, str) and github_url.strip():
        fallback_name = github_url.rstrip("/").split("/")[-1] or fallback_name

    return AnalyzeResponse(
        skill_name=fallback_name,
        overall_score=float(row.get("overall_score") or 0),
        trust_badge=row.get("trust_badge") or "Unknown",
        security=row.get("security_data") or {},
        quality=row.get("quality_data") or {},
        behavior=row.get("behavior_data") or {},
        dependencies=row.get("dependency_data") or {},
        analyzed_at=analyzed,
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_skill(payload: AnalyzeRequest) -> AnalyzeResponse:
    skill_content = payload.skill_content or ""
    content_hash = compute_content_hash(skill_content)

    try:
        cached = await get_cached_analysis(content_hash)
        if cached:
            return _to_response_from_cache(cached)
    except Exception:
        # Keep endpoint resilient if cache backend is unavailable.
        pass

    inferred_name = payload.official_skill_name or "uploaded-skill"
    if payload.source_type == "github" and payload.github_url:
        inferred_name = payload.github_url.rstrip("/").split("/")[-1] or inferred_name

    response = AnalyzeResponse(
        skill_name=inferred_name,
        overall_score=87.5,
        trust_badge="✓ Generally Safe",
        security={
            "risk_level": "low",
            "findings": [],
            "summary": "No critical findings in stub analysis.",
        },
        quality={"grade": "B+", "summary": "Documentation appears adequate (stub)."},
        behavior={
            "category": "API integration",
            "execution_steps": ["Load inputs", "Process skill", "Return results"],
        },
        dependencies={"python_packages": [], "external_apis": []},
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )

    cache_until = None
    now = datetime.now(timezone.utc)
    if payload.source_type == "github":
        cache_until = (now + timedelta(hours=24)).isoformat()
    elif payload.source_type == "official":
        cache_until = (now + timedelta(days=7)).isoformat()

    record = {
        "id": str(uuid4()),
        "github_url": payload.github_url,
        "content_hash": content_hash,
        "overall_score": response.overall_score,
        "trust_badge": response.trust_badge,
        "security_data": response.security,
        "quality_data": response.quality,
        "behavior_data": response.behavior,
        "dependency_data": response.dependencies,
        "cache_until": cache_until,
        "analyzed_at": response.analyzed_at,
    }

    try:
        await store_analysis(record)
    except Exception:
        # Keep endpoint resilient if cache backend is unavailable.
        pass

    return response
