from fastapi import FastAPI

from app.routers import (
    auth,
    exercises,
    foods,
    goals,
    meals,
    measurements,
    routines,
    users,
    water,
    workout_sessions,
)

app = FastAPI(title="appfit API", version="0.1.0")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(foods.router)
app.include_router(meals.router)
app.include_router(goals.router)
app.include_router(water.router)
app.include_router(measurements.router)
app.include_router(exercises.router)
app.include_router(routines.router)
app.include_router(workout_sessions.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
