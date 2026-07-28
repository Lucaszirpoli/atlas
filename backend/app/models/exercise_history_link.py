from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ExerciseHistoryLink(Base):
    """"Este exercício herda o histórico daquele" — o rastro de uma troca de
    exercício em que a pessoa escolheu MANTER os registros (spec §8.1).

    Por que um link, e não copiar as séries: histórico é append-only (regra 4).
    As séries do exercício antigo continuam onde sempre estiveram, ligadas ao
    exercise_id antigo. O link diz apenas "quando for pré-preencher o novo
    exercício e ele ainda não tiver registro próprio, leia os do antigo" — e
    permite mostrar a ORIGEM com clareza ("vem do Supino reto com barra").

    Escolher "começar novos registros" simplesmente NÃO cria link: o histórico
    antigo fica arquivado no exercício de origem, intacto e nunca apagado.
    """

    __tablename__ = "exercise_history_links"
    __table_args__ = (UniqueConstraint("user_id", "exercise_id", name="uq_exercise_history_link"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Exercício NOVO (o que entrou no lugar).
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), index=True)
    # Exercício ANTIGO, de onde o histórico é herdado.
    inherits_from_exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
