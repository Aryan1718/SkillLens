from fastapi import APIRouter

router = APIRouter(tags=["skills"])


@router.get("/skills")
async def list_skills() -> list[dict[str, str]]:
    return [
        {"name": "pdf-converter", "source": "official"},
        {"name": "repo-summarizer", "source": "official"},
    ]
