from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.workout_session import SetType
from app.schemas.exercise import ExerciseRead


class WorkoutSessionStart(BaseModel):
    routine_id: int


class LastSetPerformance(BaseModel):
    set_number: int
    weight_kg: float
    reps: int


class ExercisePrefill(BaseModel):
    exercise_id: int
    last_performed_at: datetime | None
    sets: list[LastSetPerformance]


class WorkoutSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    routine_id: int
    started_at: datetime
    completed_at: datetime | None


class WorkoutSessionStartResponse(BaseModel):
    session: WorkoutSessionRead
    prefill: list[ExercisePrefill]


class WorkoutSetLogCreate(BaseModel):
    exercise_id: int
    exercise_sort_order: int = 0
    set_number: int = Field(ge=1)
    weight_kg: float = Field(ge=0)
    reps: int = Field(ge=0)
    set_type: SetType = SetType.STRAIGHT
    rpe: float | None = Field(default=None, ge=0, le=10)
    rir: int | None = Field(default=None, ge=0, le=10)


class WorkoutSetLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    exercise: ExerciseRead
    exercise_sort_order: int
    set_number: int
    weight_kg: float
    reps: int
    set_type: SetType
    rpe: float | None
    rir: int | None
    completed_at: datetime


class WorkoutSessionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    routine_id: int
    started_at: datetime
    completed_at: datetime | None
    sets: list[WorkoutSetLogRead]


class WorkoutSessionSummary(BaseModel):
    session: WorkoutSessionDetail
    total_volume_kg: float
    duration_seconds: int
    previous_session_volume_kg: float | None
    volume_change_percent: float | None
