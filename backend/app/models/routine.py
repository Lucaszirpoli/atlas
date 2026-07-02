from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Routine(Base):
    """Rotina = o molde salvo e reutilizável (ex: 'Treino A - Peito e
    Tríceps'). Não é a execução em si — isso é WorkoutSession. Arquivar
    preserva o histórico de sessões já feitas, mas tira do limite de rotinas
    ativas (3 Free / 7 Pro)."""

    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    exercises: Mapped[list["RoutineExercise"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan", order_by="RoutineExercise.sort_order"
    )


class RoutineExercise(Base):
    """Um exercício dentro do molde da rotina, com a meta (não os números
    reais — esses ficam na sessão)."""

    __tablename__ = "routine_exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id", ondelete="CASCADE"))
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    target_sets: Mapped[int] = mapped_column(Integer)
    target_reps_min: Mapped[int] = mapped_column(Integer)
    target_reps_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rest_seconds: Mapped[int] = mapped_column(Integer, default=90)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    routine: Mapped["Routine"] = relationship(back_populates="exercises")
    exercise: Mapped["Exercise"] = relationship()
