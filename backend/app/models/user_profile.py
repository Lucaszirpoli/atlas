import enum
from datetime import datetime

from sqlalchemy import ARRAY, JSON, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class BiologicalSex(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"


class ActivityLevel(str, enum.Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class Goal(str, enum.Enum):
    EMAGRECIMENTO = "emagrecimento"
    HIPERTROFIA = "hipertrofia"
    MANUTENCAO = "manutencao"
    PERFORMANCE = "performance"
    RECOMPOSICAO = "recomposicao"


class ExperienceLevel(str, enum.Enum):
    INICIANTE = "iniciante"
    INTERMEDIARIO = "intermediario"
    AVANCADO = "avancado"


class TrainingLocation(str, enum.Enum):
    ACADEMIA_COMPLETA = "academia_completa"
    ACADEMIA_BASICA = "academia_basica"
    CASA_COM_EQUIPAMENTO = "casa_com_equipamento"
    CASA_SEM_EQUIPAMENTO = "casa_sem_equipamento"


class TrainingStylePreference(str, enum.Enum):
    CURTO_INTENSO = "curto_intenso"
    LONGO_VOLUMOSO = "longo_volumoso"
    IA_DECIDE = "ia_decide"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )

    biological_sex: Mapped[BiologicalSex] = mapped_column(
        Enum(BiologicalSex, name="biological_sex")
    )
    age: Mapped[int]
    height_cm: Mapped[float]
    activity_level: Mapped[ActivityLevel] = mapped_column(
        Enum(ActivityLevel, name="activity_level")
    )
    goal: Mapped[Goal] = mapped_column(Enum(Goal, name="goal"))
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        Enum(ExperienceLevel, name="experience_level")
    )
    training_location: Mapped[TrainingLocation] = mapped_column(
        Enum(TrainingLocation, name="training_location")
    )
    training_style_preference: Mapped[TrainingStylePreference] = mapped_column(
        Enum(TrainingStylePreference, name="training_style_preference"),
        default=TrainingStylePreference.IA_DECIDE,
    )

    available_days: Mapped[list[str]] = mapped_column(
        ARRAY(String(10)).with_variant(JSON(), "sqlite"), default=list
    )
    dietary_restrictions: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)).with_variant(JSON(), "sqlite"), default=list
    )
    injuries_limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_advanced_technique: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    trains_with_partner: Mapped[bool] = mapped_column(default=False)
    partner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(
        back_populates="profile", foreign_keys=[user_id]
    )
