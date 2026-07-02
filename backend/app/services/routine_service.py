from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.routine import Routine
from app.models.user import Plan

ACTIVE_ROUTINE_LIMITS: dict[Plan, int] = {
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
    return count_active_routines(db, user_id) < ACTIVE_ROUTINE_LIMITS[plan]
