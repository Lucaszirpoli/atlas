from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CoachingTechniqueCue(Base):
    """Dica de técnica de intensidade que o Coaching aplicou a um exercício
    travado (ex.: 'rest-pause no Supino'). É um OVERLAY do coach por exercício,
    não uma alteração da rotina-molde — que nem tem campo de técnica (regra 3:
    rotina ≠ sessão; a técnica é conceito de execução). A prévia do treino lê as
    dicas ativas e mostra em cima do exercício correspondente.

    Append-only + reversível: aplicar cria uma linha; 'remover' preenche
    reverted_at (não deleta). Espelha o propor → aceitar → reverter da dieta.
    Tabela nova (criada pelo create_all no deploy), então não precisa de ALTER.
    """

    __tablename__ = "coaching_technique_cues"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    finding_key: Mapped[str] = mapped_column(String(50))

    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), index=True)
    exercise_name: Mapped[str] = mapped_column(String(120))  # snapshot p/ exibir
    technique: Mapped[str] = mapped_column(String(30))       # chave (bate com SetType)
    technique_label: Mapped[str] = mapped_column(String(40))
    cue_text: Mapped[str] = mapped_column(Text)              # o "como fazer"

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Preenchido quando o usuário remove a dica. Não-nulo = inativa (não aparece
    # na prévia), mas fica no histórico.
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
