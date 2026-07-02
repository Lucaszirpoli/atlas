import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ConsentType(str, enum.Enum):
    LGPD_HEALTH_DATA = "lgpd_health_data"
    MEDICAL_DISCLAIMER = "medical_disclaimer"


class ConsentRecord(Base):
    """Registro de consentimento LGPD. Append-only: uma nova aceitação de uma
    versão de termo gera um novo registro, nunca sobrescreve o anterior."""

    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    consent_type: Mapped[ConsentType] = mapped_column(
        Enum(ConsentType, name="consent_type")
    )
    version: Mapped[str] = mapped_column(String(20))
    accepted: Mapped[bool]
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="consent_records")
