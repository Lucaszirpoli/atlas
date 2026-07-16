import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ChallengeMetric(str, enum.Enum):
    WORKOUT_COUNT = "workout_count"
    TOTAL_VOLUME = "total_volume"
    STREAK_DAYS = "streak_days"
    # "Quem vai mais à academia": conta check-ins com prova de localização
    # (ver app/models/gym.py) — não treinos registrados à mão.
    GYM_CHECKIN = "gym_checkin"


class Challenge(Base):
    """Desafio entre amigos/grupo (espec. 3.5). O placar é calculado em
    runtime a partir do histórico de treino de cada participante dentro do
    período — não é um contador incrementado manualmente."""

    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    metric: Mapped[ChallengeMetric] = mapped_column(Enum(ChallengeMetric, name="challenge_metric"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    participants: Mapped[list["ChallengeParticipant"]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan"
    )


class ChallengeParticipant(Base):
    __tablename__ = "challenge_participants"
    __table_args__ = (UniqueConstraint("challenge_id", "user_id", name="uq_challenge_participant"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    challenge: Mapped["Challenge"] = relationship(back_populates="participants")
