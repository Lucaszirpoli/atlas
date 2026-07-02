from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.weight_log import WeightLog
from app.schemas.weight import WeightLogCreate, WeightLogRead

router = APIRouter(prefix="/weight", tags=["weight"])


@router.get("", response_model=list[WeightLogRead])
def list_weight_logs(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[WeightLog]:
    stmt = (
        select(WeightLog)
        .where(WeightLog.user_id == current_user.id)
        .order_by(WeightLog.recorded_at.desc())
    )
    return list(db.execute(stmt).scalars())


@router.post("", response_model=WeightLogRead, status_code=status.HTTP_201_CREATED)
def log_weight(
    payload: WeightLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeightLog:
    log = WeightLog(
        user_id=current_user.id,
        weight_kg=payload.weight_kg,
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
