from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.body_measurement import MeasurementType


class BodyMeasurementCreate(BaseModel):
    type: MeasurementType
    value_cm: float = Field(gt=0, le=300)
    recorded_at: datetime | None = None


class BodyMeasurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: MeasurementType
    value_cm: float
    recorded_at: datetime


class ProgressPhotoCreate(BaseModel):
    photo_url: str = Field(min_length=1, max_length=500)
    recorded_at: datetime | None = None


class ProgressPhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    photo_url: str
    recorded_at: datetime
