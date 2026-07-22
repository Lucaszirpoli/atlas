from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CoachingFinding(BaseModel):
    key: str
    severity: str  # info | attention | action
    title: str
    detail: str
    proposal: str | None = None
    # Presente só quando o ajuste é aplicável (ex.: {"kcal_delta": -200}).
    adjustment: dict[str, Any] | None = None


class ApplyDietRequest(BaseModel):
    finding_key: str


class ApplyDietResult(BaseModel):
    applied: bool
    previous_kcal: float
    new_kcal: float
    kcal_delta: int
    message: str


class CoachingAdjustmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    finding_key: str
    kind: str
    kcal_delta: float
    prev_kcal: float
    new_kcal: float
    created_at: datetime
    reverted_at: datetime | None


class RevertResult(BaseModel):
    reverted: bool
    restored_kcal: float
    message: str


class ApplyTechniqueRequest(BaseModel):
    finding_key: str  # "stalled_lift:{exercise_id}"


class ApplyTechniqueResult(BaseModel):
    applied: bool
    exercise_name: str
    technique_label: str
    message: str


class TechniqueCueRead(BaseModel):
    """Dica ativa de técnica — a prévia do treino usa pra mostrar em cima do
    exercício correspondente."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    exercise_name: str
    technique: str
    technique_label: str
    cue_text: str
    created_at: datetime


class RemoveCueResult(BaseModel):
    removed: bool
    message: str


class ResetBaselineResult(BaseModel):
    reset: bool
    effective_from: datetime
    message: str


class CoachChatMessage(BaseModel):
    role: str  # user | assistant
    content: str


class CoachChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[CoachChatMessage] = Field(default_factory=list)


class CoachChatResponse(BaseModel):
    answer: str
    used_ai: bool


class CoachingInsight(BaseModel):
    key: str  # peso | calorias | macros | sono | carga | treino
    severity: str
    title: str
    detail: str
    chart: str | None = None
    finding_key: str | None = None
    adjustment: dict[str, Any] | None = None


class CoachingAnalysis(BaseModel):
    window_days: int
    goal: str | None
    has_enough_data: bool
    confidence: str  # alta | parcial | baixa
    headline: str
    findings: list[CoachingFinding]
    insights: list[CoachingInsight] = []
    data_gaps: list[str]
    metrics: dict[str, Any]
