from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.calorie_goal import GoalMode


class CalorieGoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mode: GoalMode
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    sodium_mg: float | None
    sugar_g: float | None
    created_at: datetime


class CalorieGoalManualCreate(BaseModel):
    kcal: float = Field(gt=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    fiber_g: float | None = None
    sodium_mg: float | None = None
    sugar_g: float | None = None


class CalorieGoalAutoSuggestion(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    current_goal: CalorieGoalRead | None
    changed_significantly: bool
