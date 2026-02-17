from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["simulate"])


class SimulateRequest(BaseModel):
    skill_content: str
    user_inputs: dict = Field(default_factory=dict)


class SimulateResponse(BaseModel):
    execution_steps: list[str]
    expected_outputs: dict
    security_warnings: list[str]


@router.post("/simulate", response_model=SimulateResponse)
async def simulate_skill(_: SimulateRequest) -> SimulateResponse:
    return SimulateResponse(
        execution_steps=[
            "Parse skill instructions",
            "Validate provided user inputs",
            "Simulate safe execution preview",
        ],
        expected_outputs={
            "files_created": [],
            "api_calls": [],
            "result": "Simulation complete (stub)",
        },
        security_warnings=[],
    )
