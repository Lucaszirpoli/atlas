import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class GoalMode(str, enum.Enum):
    MANUAL = "manual"
    AUTO = "auto"


class CalorieGoal(Base):
    """Meta calórica/macro vigente. Append-only: uma nova meta é uma nova
    linha, nunca sobrescreve a anterior — a meta 'atual' é sempre a mais
    recente. Isso preserva o histórico de metas ao longo do tempo."""

    __tablename__ = "calorie_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    mode: Mapped[GoalMode] = mapped_column(Enum(GoalMode, name="goal_mode"))

    kcal: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    sodium_mg: Mapped[float | None] = mapped_column(Float, nullable=True)
    sugar_g: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
