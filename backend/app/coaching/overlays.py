"""Coerência dos overlays de treino do coach (progressão, troca de exercício,
deload e dicas de técnica).

Dois cuidados que evitam o coach se contradizer no lado do treino:

1. Ao REDEFINIR o objetivo (novo marco/baseline), os overlays da fase anterior
   ficam obsoletos — foram derivados de dados que a análise não olha mais. Este
   módulo os revERTE (nunca deleta — regra 4), pra o treino recomeçar limpo.

2. "Subir carga" e "trocar exercício" no MESMO exercício se contradizem (um
   manda progredir, o outro manda substituir). Aplicar um reverte o outro.

Nenhuma função aqui dá commit — quem chama controla a transação.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.coaching_action import CoachingAction
from app.models.coaching_technique_cue import CoachingTechniqueCue


def clear_training_overlays(db: Session, user_id: int) -> int:
    """Reverte TODOS os overlays de treino ativos do usuário — ações
    (progressão/troca/deload) e dicas de técnica. Usado quando o objetivo é
    redefinido: os overlays vinham da fase anterior e não valem mais. Devolve
    quantos foram revertidos. Não commita."""
    now = datetime.now(timezone.utc)
    n = 0
    for act in db.execute(
        select(CoachingAction).where(
            CoachingAction.user_id == user_id,
            CoachingAction.reverted_at.is_(None),
        )
    ).scalars():
        act.reverted_at = now
        n += 1
    for cue in db.execute(
        select(CoachingTechniqueCue).where(
            CoachingTechniqueCue.user_id == user_id,
            CoachingTechniqueCue.reverted_at.is_(None),
        )
    ).scalars():
        cue.reverted_at = now
        n += 1
    return n


def revert_conflicting_action(db: Session, user_id: int, exercise_id: int, keep_kind: str) -> None:
    """Progressão e troca no MESMO exercício se contradizem — mata o paradoxo
    ("suba a carga do supino" convivendo com "troque o supino"). Ao aplicar uma
    (`keep_kind`), reverte a ativa do tipo oposto no mesmo exercício. Não commita."""
    other = "exercise_swap" if keep_kind == "progression" else "progression"
    now = datetime.now(timezone.utc)
    for act in db.execute(
        select(CoachingAction).where(
            CoachingAction.user_id == user_id,
            CoachingAction.exercise_id == exercise_id,
            CoachingAction.kind == other,
            CoachingAction.reverted_at.is_(None),
        )
    ).scalars():
        act.reverted_at = now
