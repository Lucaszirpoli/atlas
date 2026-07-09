from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.routine import Routine
from app.models.user import Plan

# Rotinas ativas são ILIMITADAS em ambos os planos (decisão do produto,
# 2026-07-08): o produto manual é 100% livre e a monetização fica só na IA
# (Pro). `None` = sem teto. Mantido como dict pra compat com quem lê daqui.
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
