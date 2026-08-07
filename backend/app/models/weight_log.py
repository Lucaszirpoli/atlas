from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class WeightLog(Base):
    """Histórico de peso, append-only — nunca fazer UPDATE/DELETE do valor
    registrado. É a base dos gráficos de evolução (espec. seção 3.8)."""

    __tablename__ = "weight_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    weight_kg: Mapped[float]
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Mesma chave anti-duplicata de meal_logs: o app manda uma por tentativa de
    # registro, e o retry automático de rede (resposta perdida) reenvia a MESMA
    # chave — o backend devolve o registro já criado em vez de gravar de novo.
    # Conserta o "adicionei meu peso e bugou, adicionou 3x".
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="weight_logs")
