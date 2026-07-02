from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.sleep_log import WakeFeeling


class SleepLogCreate(BaseModel):
    sleep_at: datetime
    wake_at: datetime
    quality: int = Field(ge=1, le=5)
    wake_feeling: WakeFeeling
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def wake_after_sleep(self) -> "SleepLogCreate":
        if self.wake_at <= self.sleep_at:
            raise ValueError("Horário de acordar precisa ser depois do horário de dormir")
        return self


class SleepLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sleep_at: datetime
    wake_at: datetime
    quality: int
    wake_feeling: WakeFeeling
    notes: str | None
    duration_minutes: int
