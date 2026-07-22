from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CoachingBaseline(Base):
    """Marco de recomeço da análise do Coaching. Quando a pessoa troca de
    objetivo (ex.: de ganho pra corte), analisar a média do período antigo
    mistura duas fases e engana — então ela pode recomeçar a análise a partir
    dali. O coach passa a olhar só os dados DESDE este marco.

    NÃO apaga histórico (regra 4: tudo é append-only): peso, refeições e treinos
    seguem intactos e os gráficos continuam mostrando tudo. Isto só move o ponto
    de partida da LEITURA do coach. Append-only também aqui: cada recomeço é uma
    linha nova; a mais recente é a que vale.

    Tabela nova (criada pelo create_all no deploy), então não precisa de ALTER.
    """

    __tablename__ = "coaching_baselines"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # A partir de quando a análise do coach deve considerar os dados.
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(30), default="goal_change")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
