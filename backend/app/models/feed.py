import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class FeedPostType(str, enum.Enum):
    WORKOUT = "workout"
    MEAL = "meal"
    PROGRESS_PHOTO = "progress_photo"


class FeedPost(Base):
    """Post no feed social. WORKOUT é auto-gerado ao concluir uma sessão de
    treino, se a privacidade do usuário permitir (share_workouts). MEAL e
    PROGRESS_PHOTO são sempre opt-in explícito por post (espec. 3.5)."""

    __tablename__ = "feed_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    post_type: Mapped[FeedPostType] = mapped_column(Enum(FeedPostType, name="feed_post_type"))
    reference_id: Mapped[int] = mapped_column(Integer)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship()
    reactions: Mapped[list["FeedReaction"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    comments: Mapped[list["FeedComment"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )


class FeedReaction(Base):
    __tablename__ = "feed_reactions"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_reaction_post_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("feed_posts.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    emoji: Mapped[str] = mapped_column(String(8), default="👍")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    post: Mapped["FeedPost"] = relationship(back_populates="reactions")


class FeedComment(Base):
    __tablename__ = "feed_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("feed_posts.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(String(280))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    post: Mapped["FeedPost"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship()
