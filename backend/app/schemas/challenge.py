from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.challenge import ChallengeMetric
from app.schemas.friend import UserSummary


class ChallengeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    metric: ChallengeMetric
    start_date: date
    end_date: date
    invite_handles: list[str] = Field(default_factory=list)


class ChallengeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    metric: ChallengeMetric
    start_date: date
    end_date: date
    creator_id: int
    created_at: datetime


class LeaderboardEntry(BaseModel):
    user: UserSummary
    value: float


class ChallengeLeaderboard(BaseModel):
    challenge: ChallengeRead
    entries: list[LeaderboardEntry]
