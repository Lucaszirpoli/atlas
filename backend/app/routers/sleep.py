from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.sleep_log import SleepLog
from app.models.user import User
from app.schemas.sleep import SleepLogCreate, SleepLogRead

router = APIRouter(prefix="/sleep", tags=["sleep"])


def _serialize(log: SleepLog) -> dict:
    duration = int((log.wake_at - log.sleep_at).total_seconds() // 60)
    return {
        "id": log.id,
        "sleep_at": log.sleep_at,
        "wake_at": log.wake_at,
        "quality": log.quality,
        "wake_feeling": log.wake_feeling,
        "notes": log.notes,
        "duration_minutes": duration,
    }


@router.get("", response_model=list[SleepLogRead])
def list_sleep_logs(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = (
        select(SleepLog)
        .where(SleepLog.user_id == current_user.id)
        .order_by(SleepLog.sleep_at.desc())
        .limit(limit)
    )
    return [_serialize(log) for log in db.execute(stmt).scalars()]


@router.post("", response_model=SleepLogRead, status_code=status.HTTP_201_CREATED)
def log_sleep(
    payload: SleepLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    log = SleepLog(
        user_id=current_user.id,
        sleep_at=payload.sleep_at,
        wake_at=payload.wake_at,
        quality=payload.quality,
        wake_feeling=payload.wake_feeling,
        notes=payload.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return _serialize(log)


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sleep_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    log = db.get(SleepLog, log_id)
    if log is None or log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro não encontrado")
    db.delete(log)
    db.commit()
