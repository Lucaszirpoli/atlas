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
