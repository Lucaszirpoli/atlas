from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.routine import Routine
from app.models.user import Plan

# Limite de rotinas ativas por plano — regra de negócio da Parte 4 da
# especificação (não simplificar sem confirmar): 3 no Free, 7 no Pro.
# Rotinas arquivadas não contam pro limite.
ACTIVE_ROUTINE_LIMITS: dict[Plan, int | None] = {
    Plan.FREE: 3,
    Plan.PRO: 7,
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
