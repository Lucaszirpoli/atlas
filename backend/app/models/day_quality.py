import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DayMarkStatus(str, enum.Enum):
    """Decisão do USUÁRIO sobre um dia cujo registro alimentar parece
    incompleto (spec §10.2). Enquanto ele não decide, o dia fica pendente e
    fora das médias."""

    # "Aceitar como está": os dados representam o dia mesmo. Entra nas médias
    # com marcação de confirmação manual.
    CONFIRMED = "confirmed"
    # "Marcar como incompleto": preserva os registros, mas o dia sai das médias
    # nutricionais (ainda conta na métrica de adesão AO REGISTRO).
    INCOMPLETE = "incomplete"


class NutritionDayMark(Base):
    """Marcação manual de qualidade do registro alimentar de UM dia.

    Existe pra o coach não assumir que 400 kcal registradas foram a ingestão
    real de um dia inteiro. Sem marcação, o dia é classificado automaticamente
    (ver services/day_quality.py); com marcação, a palavra do usuário vence.
    """

    __tablename__ = "nutrition_day_marks"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_nutrition_day_mark"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Dia de CALENDÁRIO da pessoa (no fuso dela), não um instante.
    day: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[DayMarkStatus] = mapped_column(
        Enum(DayMarkStatus, name="day_mark_status", native_enum=False)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
