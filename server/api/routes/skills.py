import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from core.cache import get_supabase

router = APIRouter(tags=["skills"])


@router.get("/skills")
async def get_skills() -> list[dict[str, Any]]:
    skills = await _list_skills(limit=500)
    analysis_by_skill = await _list_latest_analyses([row["id"] for row in skills if row.get("id")])

    items: list[dict[str, Any]] = []
    for row in skills:
        row_id = row.get("id")
        analysis = analysis_by_skill.get(row_id, {})
        items.append(
            {
                "id": row_id,
                "name": row.get("name") or row.get("skill_slug"),
                "source": row.get("source"),
                "owner": row.get("owner"),
                "repo": row.get("repo"),
                "skill_slug": row.get("skill_slug"),
                "page_url": row.get("page_url"),
                "repository_url": row.get("repository_url"),
                "weekly_installs": row.get("weekly_installs"),
                "last_seen_at": row.get("last_seen_at"),
                "trust_badge": analysis.get("trust_badge"),
                "overall_score": analysis.get("overall_score"),
            }
        )
    return items


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str) -> dict[str, Any]:
    row = await _get_skill_by_id(skill_id)
    if not row:
        raise HTTPException(status_code=404, detail="Skill not found")

    analysis = await _get_latest_analysis(skill_id)
    return {
        "id": row.get("id"),
        "name": row.get("name") or row.get("skill_slug"),
        "owner": row.get("owner"),
        "repo": row.get("repo"),
        "skill_slug": row.get("skill_slug"),
        "page_url": row.get("page_url"),
        "repository_url": row.get("repository_url"),
        "install_command": row.get("install_command"),
        "weekly_installs": row.get("weekly_installs") or 0,
        "skill_md_rendered": row.get("skill_md_rendered") or row.get("skill_content") or "",
        "extracted_links": row.get("extracted_links") or [],
        "scraped_at": row.get("scraped_at"),
        "last_seen_at": row.get("last_seen_at"),
        "analysis": {
            "overall_score": analysis.get("overall_score"),
            "trust_badge": analysis.get("trust_badge"),
            "security": analysis.get("security_data"),
            "quality": analysis.get("quality_data"),
            "behavior": analysis.get("behavior_data"),
            "dependencies": analysis.get("dependency_data"),
            "analyzed_at": analysis.get("completed_at") or analysis.get("created_at"),
        },
    }


async def _list_skills(limit: int) -> list[dict[str, Any]]:
    def _query() -> list[dict[str, Any]]:
        response = (
            get_supabase()
            .table("skills")
            .select(
                "id,name,source,owner,repo,skill_slug,page_url,repository_url,"
                "weekly_installs,last_seen_at"
            )
            .order("weekly_installs", desc=True)
            .order("last_seen_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    return await asyncio.to_thread(_query)


async def _get_skill_by_id(skill_id: str) -> dict[str, Any] | None:
    def _query() -> dict[str, Any] | None:
        response = (
            get_supabase()
            .table("skills")
            .select(
                "id,name,owner,repo,skill_slug,page_url,repository_url,install_command,"
                "weekly_installs,skill_md_rendered,skill_content,extracted_links,scraped_at,last_seen_at"
            )
            .eq("id", skill_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    return await asyncio.to_thread(_query)


async def _list_latest_analyses(skill_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not skill_ids:
        return {}

    def _query() -> list[dict[str, Any]]:
        response = (
            get_supabase()
            .table("skill_analyses")
            .select(
                "skill_id,status,overall_score,trust_badge,security_data,quality_data,"
                "behavior_data,dependency_data,completed_at,created_at"
            )
            .in_("skill_id", skill_ids)
            .in_("status", ["completed", "success", "succeeded"])
            .order("completed_at", desc=True)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []

    try:
        rows = await asyncio.to_thread(_query)
    except Exception:
        return {}

    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        skill_id = row.get("skill_id")
        if skill_id and skill_id not in latest:
            latest[skill_id] = row
    return latest


async def _get_latest_analysis(skill_id: str) -> dict[str, Any]:
    def _query() -> list[dict[str, Any]]:
        response = (
            get_supabase()
            .table("skill_analyses")
            .select(
                "skill_id,status,overall_score,trust_badge,security_data,quality_data,"
                "behavior_data,dependency_data,completed_at,created_at"
            )
            .eq("skill_id", skill_id)
            .in_("status", ["completed", "success", "succeeded"])
            .order("completed_at", desc=True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return response.data or []

    try:
        rows = await asyncio.to_thread(_query)
    except Exception:
        return {}
    return rows[0] if rows else {}
