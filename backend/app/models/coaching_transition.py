from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CoachingTransition(Base):
    """Transição de objetivo em andamento. Quando a pessoa troca de objetivo e a
    meta de calorias mudaria MUITO (ex.: sair de um corte pra um bulk), o coach
    NÃO estoura tudo de um dia pro outro — aplica um passo capado e marca esta
    transição. Depois, a cada poucos dias, oferece o próximo passo até chegar no
    alvo do novo objetivo. É o que faz o coach parecer um treinador de verdade,
    que sabe fazer a transição sem chocar o corpo.

    `to_objective` é só rótulo pra UI; o ALVO real é recalculado a cada passo
    (`goal_service.compute_suggestion`), então acompanha mudanças de peso.
    Append-only + reversível-por-conclusão (completed_at). Tabela nova (create_all).
    """

    __tablename__ = "coaching_transitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    to_objective: Mapped[str] = mapped_column(String(20))  # goal.value do destino
    # kcal do ponto de partida e o alvo no momento da troca (só p/ exibir progresso).
    from_kcal: Mapped[float] = mapped_column(Float)
    target_kcal: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Preenchido quando a meta chega no alvo (transição concluída) OU quando a
    # pessoa troca de objetivo de novo (a transição antiga deixa de valer).
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
