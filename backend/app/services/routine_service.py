from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.routine import Routine
from app.models.user import Plan

# Rotinas ativas ILIMITADAS (Free e Pro) — regra amendada pelo dono do produto
# depois da spec original (que dizia 3/7). Bater num teto silencioso fazia
# "salvar rotina" falhar (o motivo de uma rotina "não salvar" na aba de treino).
# None = sem limite; o resto do código (can_create/bulk) já trata None como
# "pode sempre". Arquivadas nunca contaram mesmo.
ACTIVE_ROUTINE_LIMITS: dict[Plan, int | None] = {
    Plan.FREE: None,
    Plan.PRO: None,
}


def count_active_routines(db: Session, user_id: int) -> int:
    return db.execute(
        select(func.count())
        .select_from(Routine)
        .where(Routine.user_id == user_id, Routine.is_archived.is_(False))
    ).scalar_one()


def can_create_active_routine(db: Session, user_id: int, plan: Plan) -> bool:
    limit = ACTIVE_ROUTINE_LIMITS[plan]
    if limit is None:
        return True
    return count_active_routines(db, user_id) < limit
