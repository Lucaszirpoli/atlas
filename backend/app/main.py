from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers import (
    ai,
    assistant,
    auth,
    billing,
    blocks,
    challenges,
    diet_templates,
    evolution,
    exercises,
    feed,
    foods,
    friends,
    goals,
    gyms,
    meals,
    measurements,
    privacy,
    reports,
    routines,
    sleep,
    users,
    water,
    weight,
    workout_insights,
    workout_sessions,
)

app = FastAPI(title="appfit API", version="0.1.0")

# CORS: o app React Native na web (Expo Web) roda numa origem diferente da API
# e o navegador faz preflight OPTIONS. Sem isso, nenhuma chamada de browser
# passa. As origens permitidas são configuráveis por ambiente.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    # Autenticação é via Bearer token no header Authorization, não cookies —
    # então não precisamos de credentials, e isso mantém o wildcard "*" válido.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(assistant.router)
app.include_router(users.router)
app.include_router(foods.router)
app.include_router(meals.router)
app.include_router(diet_templates.router)
app.include_router(billing.router)
app.include_router(goals.router)
app.include_router(water.router)
app.include_router(weight.router)
app.include_router(measurements.router)
app.include_router(exercises.router)
app.include_router(routines.router)
app.include_router(workout_sessions.router)
app.include_router(ai.router)
app.include_router(friends.router)
app.include_router(blocks.router)
app.include_router(reports.router)
app.include_router(privacy.router)
app.include_router(feed.router)
app.include_router(challenges.router)
app.include_router(gyms.router)
app.include_router(sleep.router)
app.include_router(workout_insights.router)
app.include_router(evolution.router)

# GIFs de exercício baixados da ExerciseDB (ver scripts/backfill_exercise_images.py)
# ficam aqui até migrarmos pra um bucket S3-compatible (Cloudflare R2) em produção.
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
