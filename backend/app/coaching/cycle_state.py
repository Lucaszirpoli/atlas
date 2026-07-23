"""Estado de ciclo do usuário (periodização escolhida, há quantas semanas está
acumulando) — compartilhado entre o router do Coaching (análise/chat) e o
fluxo de treino (sugestão de RIR na prévia/execução), pra não duplicar a
mesma consulta em dois lugares e arriscar os dois discordarem."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coaching import training_brain
from app.models.coaching_action import CoachingAction
from app.models.coaching_baseline import CoachingBaseline
from app.models.user import User


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite (dev) devolve datetime naive; Postgres aware. Normaliza pra UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def periodization_of(user: User) -> str:
    profile = getattr(user, "profile", None)
    return training_brain.valid_periodization(getattr(profile, "periodization", None))


def weeks_accumulating(db: Session, user_id: int, now: datetime) -> float | None:
    """Semanas acumulando desde o começo do ciclo atual — o marco é o ÚLTIMO
    deload aplicado (mesmo já terminado); sem deload, o início do objetivo
    (baseline). None = sem referência."""
    ref = _aware(db.execute(
        select(CoachingAction.created_at)
        .where(
            CoachingAction.user_id == user_id,
            CoachingAction.kind == "deload",
            CoachingAction.reverted_at.is_(None),
        )
        .order_by(CoachingAction.created_at.desc(), CoachingAction.id.desc())
        .limit(1)
    ).scalar_one_or_none())
    if ref is None:
        ref = _aware(db.execute(
            select(CoachingBaseline.effective_from)
            .where(CoachingBaseline.user_id == user_id)
            .order_by(CoachingBaseline.created_at.desc(), CoachingBaseline.id.desc())
            .limit(1)
        ).scalar_one_or_none())
    if ref is None:
        return None
    return max(0.0, (now - ref).days / 7.0)


def current_period(db: Session, user_id: int, now: datetime | None = None) -> str:
    """'acumulacao' ou 'intensificacao' agora, pro usuário — usado pra sugerir
    RIR de série de trabalho e pra escolher técnica avançada."""
    now = now or datetime.now(timezone.utc)
    return training_brain.training_period(weeks_accumulating(db, user_id, now))
