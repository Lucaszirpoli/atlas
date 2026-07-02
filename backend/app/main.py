from fastapi import FastAPI

from app.routers import auth, foods, goals, meals, measurements, users, water

app = FastAPI(title="appfit API", version="0.1.0")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(foods.router)
app.include_router(meals.router)
app.include_router(goals.router)
app.include_router(water.router)
app.include_router(measurements.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
