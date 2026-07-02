from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.feed import FeedPostType
from app.schemas.friend import UserSummary


class ShareMealRequest(BaseModel):
    meal_log_id: int
    caption: str | None = Field(default=None, max_length=280)


class ShareProgressPhotoRequest(BaseModel):
    progress_photo_id: int
    caption: str | None = Field(default=None, max_length=280)


class FeedCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=280)


class FeedCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author: UserSummary
    content: str
    created_at: datetime


class FeedReactionCreate(BaseModel):
    emoji: str = Field(default="👍", max_length=8)


class FeedPostRead(BaseModel):
    id: int
    author: UserSummary
    post_type: FeedPostType
    reference_id: int
    caption: str | None
    created_at: datetime
    summary: dict
    reaction_count: int
    my_reaction: str | None
    comments: list[FeedCommentRead]
