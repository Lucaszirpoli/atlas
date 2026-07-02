import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProfileVisibility(str, enum.Enum):
    PRIVATE = "private"  # só amigos veem
    PUBLIC = "public"


class UserPrivacySettings(Base):
    """Privacidade granular (espec. 3.5): perfil privado por padrão, e o
    usuário escolhe especificamente o que compartilha no feed — ex: pode
    compartilhar treino mas não peso/fotos."""

    __tablename__ = "user_privacy_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    profile_visibility: Mapped[ProfileVisibility] = mapped_column(
        Enum(ProfileVisibility, name="profile_visibility"), default=ProfileVisibility.PRIVATE
    )
    share_workouts: Mapped[bool] = mapped_column(Boolean, default=True)
    share_meals: Mapped[bool] = mapped_column(Boolean, default=False)
    share_progress_photos: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
