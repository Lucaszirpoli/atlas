import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WakeFeeling(str, enum.Enum):
    DESCANSADO = "descansado"
    CANSADO = "cansado"
    MUITO_CANSADO = "muito_cansado"


class SleepLog(Base):
    """Registro de sono, append-only (espec. 3.4). Duração é derivada de
    wake_at - sleep_at, nunca armazenada como número solto que possa
    divergir dos horários reais."""

    __tablename__ = "sleep_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sleep_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    wake_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quality: Mapped[int] = mapped_column(Integer)  # 1-5
    wake_feeling: Mapped[WakeFeeling] = mapped_column(Enum(WakeFeeling, name="wake_feeling"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
