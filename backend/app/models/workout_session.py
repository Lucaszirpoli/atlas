import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class SetType(str, enum.Enum):
    WARMUP = "warmup"
    STRAIGHT = "straight"  # série válida (padrão)
    FEEDER = "feeder"  # preparatória — série leve entre o aquecimento e a série valendo
    DROP_SET = "drop_set"
    REST_PAUSE = "rest_pause"
    MYO_REPS = "myo_reps"
    CLUSTER_SET = "cluster_set"
    TO_FAILURE = "to_failure"
    TECHNICAL_FAILURE = "technical_failure"
    TEMPO = "tempo"
    ECCENTRIC_EMPHASIS = "eccentric_emphasis"
    PRE_EXHAUSTION = "pre_exhaustion"
    SUPERSET = "superset"
    BISET = "biset"
    TRISET = "triset"
    CIRCUIT = "circuit"


class WorkoutSession(Base):
    """Sessão = a execução real, numa data específica, de uma rotina salva.
    Append-only: cada treino é uma linha nova, nunca sobrescrita — é a base
    dos gráficos de evolução (carga por exercício, volume por sessão, PRs)."""

    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # SET NULL (não CASCADE): excluir a rotina não pode apagar o histórico de
    # treinos já registrados (append-only) — a sessão continua existindo, só
    # perde a referência à rotina-molde que não existe mais.
    routine_id: Mapped[int | None] = mapped_column(ForeignKey("routines.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sets: Mapped[list["WorkoutSetLog"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class WorkoutSetLog(Base):
    """Uma série executada de fato. Peso e reps são os campos centrais
    (sempre visíveis na UI); tipo de série e RPE/RIR são opcionais, ficam
    atrás de 'mais opções' e não são obrigatórios para concluir o treino."""

    __tablename__ = "workout_set_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id", ondelete="CASCADE"))
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    exercise_sort_order: Mapped[int] = mapped_column(Integer, default=0)
    set_number: Mapped[int] = mapped_column(Integer)

    weight_kg: Mapped[float] = mapped_column(Float)
    reps: Mapped[int] = mapped_column(Integer)
    set_type: Mapped[SetType] = mapped_column(Enum(SetType, name="set_type"), default=SetType.STRAIGHT)
    rpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    rir: Mapped[int | None] = mapped_column(Integer, nullable=True)

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["WorkoutSession"] = relationship(back_populates="sets")
    exercise: Mapped["Exercise"] = relationship()
