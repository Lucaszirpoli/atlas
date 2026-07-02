from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.friend_request import FriendRequestStatus


class FriendRequestCreate(BaseModel):
    handle: str = Field(min_length=3, max_length=30)


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    handle: str
    display_name: str


class FriendRequestRead(BaseModel):
    id: int
    status: FriendRequestStatus
    created_at: datetime
    other_user: UserSummary
    direction: str  # "sent" ou "received"
