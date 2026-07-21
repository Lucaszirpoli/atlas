from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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


class CoachingAnalysis(BaseModel):
    window_days: int
    goal: str | None
    has_enough_data: bool
    confidence: str  # alta | parcial | baixa
    headline: str
    findings: list[CoachingFinding]
    data_gaps: list[str]
    metrics: dict[str, Any]
