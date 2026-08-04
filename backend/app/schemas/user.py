from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import Plan


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    handle: str
    display_name: str
    plan: Plan
    onboarding_completed: bool
    ai_free_credits: int
    created_at: datetime


class HandleAvailabilityResponse(BaseModel):
    handle: str
    available: bool


class ResetDataResponse(BaseModel):
    """O que foi apagado, por tipo. A pessoa acabou de mandar apagar a própria
    história — ela merece ver o que saiu, não um 'ok' mudo."""

    apagados: dict[str, int]
    total: int
