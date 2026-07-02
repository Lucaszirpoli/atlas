from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WaterLogCreate(BaseModel):
    amount_ml: int = Field(gt=0, le=5000)
    logged_at: datetime | None = None


class WaterLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_ml: int
    logged_at: datetime


class WaterSummary(BaseModel):
    goal_ml: int
    total_ml_today: int
    logs_today: list[WaterLogRead]
