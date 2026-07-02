from pydantic import BaseModel


class PlateauEntry(BaseModel):
    exercise_id: int
    exercise_name: str
    sessions_without_progress: int
    current_weight_kg: float


class DeloadSuggestion(BaseModel):
    consecutive_weeks_trained: int
    suggested: bool
    message: str


class WorkoutInsightsResponse(BaseModel):
    plateaus: list[PlateauEntry]
    deload: DeloadSuggestion
