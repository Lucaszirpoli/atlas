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
    created_at: datetime


class HandleAvailabilityResponse(BaseModel):
    handle: str
    available: bool
