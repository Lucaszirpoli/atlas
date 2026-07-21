from typing import Any

from pydantic import BaseModel


class CoachingFinding(BaseModel):
    key: str
    severity: str  # info | attention | action
    title: str
    detail: str
    proposal: str | None = None


class CoachingAnalysis(BaseModel):
    window_days: int
    goal: str | None
    has_enough_data: bool
    confidence: str  # alta | parcial | baixa
    headline: str
    findings: list[CoachingFinding]
    data_gaps: list[str]
    metrics: dict[str, Any]
