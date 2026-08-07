from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.usertime import local_date, profile_tz
from app.models.sleep_log import SleepLog
from app.models.user import User
from app.schemas.sleep import SleepLogCreate, SleepLogRead

router = APIRouter(prefix="/sleep", tags=["sleep"])


def _serialize(log: SleepLog, tz) -> dict:
    duration = int((log.wake_at - log.sleep_at).total_seconds() // 60)
    return {
        "id": log.id,
        "sleep_at": log.sleep_at,
        "wake_at": log.wake_at,
        "quality": log.quality,
        "wake_feeling": log.wake_feeling,
        "notes": log.notes,
        "duration_minutes": duration,
        # A noite "pertence" ao dia em que a pessoa ACORDOU (fuso dela), não
        # ao dia em que deitou — dormir 23h de quinta e acordar 4h40 é a noite
        # de SEXTA. Era isto que fazia a tela mostrar "quinta" numa sexta.
        "log_date": local_date(log.wake_at, tz),
    }


@router.get("", response_model=list[SleepLogRead])
def list_sleep_logs(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    tz = profile_tz(getattr(current_user, "profile", None))
    stmt = (
        select(SleepLog)
        .where(SleepLog.user_id == current_user.id)
        .order_by(SleepLog.sleep_at.desc())
        .limit(limit)
    )
    return [_serialize(log, tz) for log in db.execute(stmt).scalars()]


@router.post("", response_model=SleepLogRead, status_code=status.HTTP_201_CREATED)
def log_sleep(
    payload: SleepLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    tz = profile_tz(getattr(current_user, "profile", None))

    # MESMA CHAVE = MESMO REGISTRO (ver meal_service.log_meal). Sem isto, o
    # retry automático do app numa rede ruim gravava a mesma noite 2-3 vezes.
    if payload.idempotency_key:
        ja = db.execute(
            select(SleepLog).where(
                SleepLog.user_id == current_user.id,
                SleepLog.idempotency_key == payload.idempotency_key,
            ).limit(1)
        ).scalar_one_or_none()
        if ja is not None:
            return _serialize(ja, tz)

    # MESMA NOITE = MESMO REGISTRO. A chave de idempotência protege o retry
    # automático dentro de UMA chamada, mas cada toque em "Registrar" gera uma
    # chave nova — se o app achou que a chamada anterior tinha falhado (ex.:
    # o backend do Railway acordando de um cold start, que passa de 30-60s) e
    # o usuário tocou de novo, as duas chamadas tinham chaves diferentes e a
    # mesma noite entrava duplicada. Sleep_at+wake_at iguais pro mesmo usuário
    # É a mesma noite, ponto — ninguém dorme duas vezes no exato mesmo minuto.
    duplicada = db.execute(
        select(SleepLog).where(
            SleepLog.user_id == current_user.id,
            SleepLog.sleep_at == payload.sleep_at,
            SleepLog.wake_at == payload.wake_at,
        ).limit(1)
    ).scalar_one_or_none()
    if duplicada is not None:
        return _serialize(duplicada, tz)

    log = SleepLog(
        user_id=current_user.id,
        sleep_at=payload.sleep_at,
        wake_at=payload.wake_at,
        quality=payload.quality,
        wake_feeling=payload.wake_feeling,
        notes=payload.notes,
        idempotency_key=payload.idempotency_key,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return _serialize(log, tz)


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
