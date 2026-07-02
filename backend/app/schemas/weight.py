from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WeightLogCreate(BaseModel):
    weight_kg: float = Field(gt=0, le=400)
    recorded_at: datetime | None = None


class WeightLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weight_kg: float
    recorded_at: datetime
