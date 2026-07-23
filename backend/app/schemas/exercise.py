from pydantic import BaseModel, ConfigDict, Field

from app.models.exercise import Difficulty, Equipment, MuscleGroup


class ExerciseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    primary_muscle_group: MuscleGroup
    secondary_muscle_groups: list[str]
    equipment: Equipment
    difficulty: Difficulty
    execution_text: str | None
    video_url: str | None
    is_custom: bool
    is_compound: bool


class ExerciseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    primary_muscle_group: MuscleGroup
    secondary_muscle_groups: list[str] = Field(default_factory=list)
    equipment: Equipment
    difficulty: Difficulty = Difficulty.BEGINNER
    execution_text: str | None = None
    video_url: str | None = None
