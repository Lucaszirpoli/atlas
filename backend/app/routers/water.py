from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.water_log import WaterLog
from app.schemas.water import WaterLogCreate, WaterLogRead, WaterSummary
from app.services import water_service

router = APIRouter(prefix="/water", tags=["water"])


@router.get("/today", response_model=WaterSummary)
def get_today_summary(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    logs = water_service.get_today_logs(db, current_user.id)
    return {
        "goal_ml": water_service.compute_goal_ml(db, current_user.id),
        "total_ml_today": sum(log.amount_ml for log in logs),
        "logs_today": logs,
    }


@router.post("", response_model=WaterLogRead, status_code=status.HTTP_201_CREATED)
def log_water(
    payload: WaterLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WaterLog:
    log = WaterLog(
        user_id=current_user.id,
        amount_ml=payload.amount_ml,
        logged_at=payload.logged_at or datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_water_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    log = db.get(WaterLog, log_id)
    if log is None or log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro não encontrado")
    db.delete(log)
    db.commit()
