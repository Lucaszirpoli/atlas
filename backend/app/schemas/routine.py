from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.exercise import ExerciseRead


class RoutineExerciseCreate(BaseModel):
    exercise_id: int
    target_sets: int = Field(ge=1, le=20)
    target_reps_min: int = Field(ge=1, le=100)
    target_reps_max: int | None = Field(default=None, ge=1, le=100)
    rest_seconds: int = Field(default=90, ge=0, le=900)
    notes: str | None = None


class RoutineExerciseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    exercise: ExerciseRead
    sort_order: int
    target_sets: int
    target_reps_min: int
    target_reps_max: int | None
    rest_seconds: int
    notes: str | None


class RoutineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    exercises: list[RoutineExerciseCreate] = Field(min_length=1)


class RoutineUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    exercises: list[RoutineExerciseCreate] = Field(min_length=1)


class RoutineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_archived: bool
    exercises: list[RoutineExerciseRead]
    created_at: datetime
