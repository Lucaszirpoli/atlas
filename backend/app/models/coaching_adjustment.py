from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CoachingAdjustment(Base):
    """Registro auditável de um ajuste que o Coaching aplicou à meta do usuário.

    Guarda o snapshot da meta ANTES do ajuste (kcal + macros) pra o "Desfazer"
    restaurar exatamente o que era — sem depender de adivinhar a versão anterior.
    É o histórico do propor → aceitar → reverter da Parte do Coaching. Tabela
    nova (criada pelo create_all no deploy), então não precisa de ALTER.
    """

    __tablename__ = "coaching_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    finding_key: Mapped[str] = mapped_column(String(50))
    kind: Mapped[str] = mapped_column(String(30), default="diet_kcal")
    kcal_delta: Mapped[float] = mapped_column(Float)

    # Snapshot da meta anterior — o que o "Desfazer" restaura.
    prev_kcal: Mapped[float] = mapped_column(Float)
    prev_protein_g: Mapped[float] = mapped_column(Float)
    prev_carbs_g: Mapped[float] = mapped_column(Float)
    prev_fat_g: Mapped[float] = mapped_column(Float)
    new_kcal: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Preenchido quando o usuário desfaz. Não-nulo = já revertido (não desfaz 2x).
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
