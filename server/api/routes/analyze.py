from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

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


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_skill(payload: AnalyzeRequest) -> AnalyzeResponse:
    inferred_name = payload.official_skill_name or "uploaded-skill"
    if payload.source_type == "github" and payload.github_url:
        inferred_name = payload.github_url.rstrip("/").split("/")[-1] or inferred_name

    return AnalyzeResponse(
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
