import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ChallengeMetric(str, enum.Enum):
    """Tipos de desafio, cobrindo os 4 módulos do app. Todos são calculados do
    histórico real (ver challenge_service). Não existe desafio de perda de peso
    de propósito — premiar isso incentiva comportamento perigoso (espec. 3.7)."""

    # --- Treino ---
    WORKOUT_COUNT = "workout_count"        # quem treina mais vezes
    TOTAL_VOLUME = "total_volume"          # carga total (peso × reps) das séries VÁLIDAS
    PR_COUNT = "pr_count"                  # quem bate mais recordes pessoais
    # --- Consistência ---
    STREAK_DAYS = "streak_days"            # maior sequência de dias treinando
    GYM_CHECKIN = "gym_checkin"            # idas à academia com prova de localização
    # --- Saúde ---
    SLEEP_NIGHTS = "sleep_nights"          # noites bem dormidas (7h+)
    WATER_GOAL_DAYS = "water_goal_days"    # dias batendo a meta de água
    # --- Dieta ---
    PROTEIN_GOAL_DAYS = "protein_goal_days"  # dias batendo a meta de proteína
    DIET_LOGGED_DAYS = "diet_logged_days"    # dias com a dieta registrada


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
