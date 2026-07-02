from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.water_log import WaterLog
from app.services.goal_service import get_latest_weight_kg

ML_PER_KG = 35
DEFAULT_GOAL_ML = 2000


def compute_goal_ml(db: Session, user_id: int) -> int:
    weight_kg = get_latest_weight_kg(db, user_id)
    if weight_kg is None:
        return DEFAULT_GOAL_ML
    return round(weight_kg * ML_PER_KG)


def get_today_logs(db: Session, user_id: int) -> list[WaterLog]:
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return list(
        db.execute(
            select(WaterLog)
            .where(WaterLog.user_id == user_id, WaterLog.logged_at >= start_of_day)
            .order_by(WaterLog.logged_at)
        ).scalars()
    )
