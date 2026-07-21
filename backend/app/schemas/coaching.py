from typing import Any

from pydantic import BaseModel


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


class CoachingAnalysis(BaseModel):
    window_days: int
    goal: str | None
    has_enough_data: bool
    confidence: str  # alta | parcial | baixa
    headline: str
    findings: list[CoachingFinding]
    data_gaps: list[str]
    metrics: dict[str, Any]
