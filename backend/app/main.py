from fastapi import FastAPI

from app.routers import (
    ai,
    auth,
    blocks,
    challenges,
    exercises,
    feed,
    foods,
    friends,
    goals,
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

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(foods.router)
app.include_router(meals.router)
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
app.include_router(sleep.router)
app.include_router(workout_insights.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
