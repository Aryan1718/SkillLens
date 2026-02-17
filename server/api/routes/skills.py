from typing import Any

from fastapi import APIRouter

from core.cache import list_skills

router = APIRouter(tags=["skills"])


@router.get("/skills")
async def get_skills() -> list[dict[str, Any]]:
    try:
        return await list_skills(limit=50)
    except Exception:
        return []
