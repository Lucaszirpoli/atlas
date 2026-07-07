import enum
from datetime import datetime

from sqlalchemy import ARRAY, JSON, Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MuscleGroup(str, enum.Enum):
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    QUADS = "quads"
    HAMSTRINGS = "hamstrings"
    GLUTES = "glutes"
    CALVES = "calves"
    ABS = "abs"
    FOREARMS = "forearms"
    TRAPS = "traps"
    FULL_BODY = "full_body"
    CARDIO = "cardio"


class Equipment(str, enum.Enum):
    BARBELL = "barbell"
    DUMBBELL = "dumbbell"
    MACHINE = "machine"
    CABLE = "cable"
    BODYWEIGHT = "bodyweight"
    KETTLEBELL = "kettlebell"
    BAND = "band"
    SMITH_MACHINE = "smith_machine"
    OTHER = "other"


class Difficulty(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Exercise(Base):
    """Biblioteca de exercícios. is_custom=True para exercícios criados por
    um usuário (com vídeo/gif próprio opcional)."""

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    primary_muscle_group: Mapped[MuscleGroup] = mapped_column(
        Enum(MuscleGroup, name="muscle_group")
    )
    secondary_muscle_groups: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)).with_variant(JSON(), "sqlite"), default=list
    )
    equipment: Mapped[Equipment] = mapped_column(Enum(Equipment, name="equipment"))
    difficulty: Mapped[Difficulty] = mapped_column(Enum(Difficulty, name="difficulty"))
    execution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
