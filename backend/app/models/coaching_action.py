from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CoachingAction(Base):
    """Ação de treino que o Coaching aplicou — o vagão genérico das mudanças que
    vão ALÉM da dieta (kcal) e da técnica de intensidade, que já têm tabela
    própria. Cobre:

    - ``progression``  : mandar subir a carga num exercício que ficou fácil.
    - ``exercise_swap``: trocar um exercício travado por uma variação (dos 50).
    - ``deload``       : semana leve (banner global no treino por ~7 dias).

    É um OVERLAY do coach, não altera a rotina-molde (regra 3) nem apaga
    histórico (regra 4). Append-only + reversível: aplicar cria uma linha;
    desfazer preenche ``reverted_at`` (não deleta). Mesmo padrão da dieta e da
    técnica. O painel 'O que o coach mudou' e os overlays do treino leem daqui.
    Tabela nova (create_all no deploy) — sem ALTER.
    """

    __tablename__ = "coaching_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)  # progression | exercise_swap | deload
    finding_key: Mapped[str] = mapped_column(String(60))

    # Alvo do overlay no treino. Null = ação global (deload) que vale pra sessão
    # inteira, não pra um exercício.
    exercise_id: Mapped[int | None] = mapped_column(
        ForeignKey("exercises.id"), nullable=True, index=True
    )
    exercise_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    title: Mapped[str] = mapped_column(String(80))   # rótulo curto p/ painel e overlay
    detail: Mapped[str] = mapped_column(Text)        # o "como fazer" / explicação
    # Números da ação (novo peso, id/nome do substituto, etc.) — o servidor
    # rederiva na hora de aplicar, isto é só o snapshot exibível.
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Não-nulo = desfeita (some dos overlays), mas fica no histórico.
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
