from datetime import datetime

from pydantic import BaseModel


class WeightPoint(BaseModel):
    date: datetime
    weight_kg: float


class VolumePoint(BaseModel):
    date: datetime
    volume_kg: float
    sets: int


class ExerciseOption(BaseModel):
    id: int
    name: str
    set_count: int


class ExerciseProgressionPoint(BaseModel):
    date: datetime
    max_weight_kg: float
    volume_kg: float


class ExerciseProgressionResponse(BaseModel):
    exercise_name: str
    points: list[ExerciseProgressionPoint]


class NutritionDay(BaseModel):
    date: str
    kcal: int
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0


class NutritionHistoryResponse(BaseModel):
    days: list[NutritionDay]
    goal_kcal: float | None
    goal_protein_g: float | None = None
    goal_carbs_g: float | None = None
    goal_fat_g: float | None = None
    days_logged: int
    days_within_goal: int


class StrengthGroup(BaseModel):
    group: str  # "superiores" | "inferiores" | "core"
    avg_pct_change: float
    exercises_count: int


class StrengthByGroupResponse(BaseModel):
    groups: list[StrengthGroup]


class ConsistencyDay(BaseModel):
    date: str
    trained: bool
    slept_well: bool
    hydrated: bool
    logged_food: bool
    score: int


class ConsistencyResponse(BaseModel):
    days: list[ConsistencyDay]
    current_streak: int
    best_streak: int
