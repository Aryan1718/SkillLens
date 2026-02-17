from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import analyze, health, simulate, skills

app = FastAPI(title="SkillLens API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(simulate.router)
app.include_router(skills.router)
