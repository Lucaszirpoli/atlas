from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.routine import Routine, RoutineExercise
from app.models.user import User
from app.models.workout_session import WorkoutSession, WorkoutSetLog
from app.schemas.workout_session import (
    WorkoutSessionDetail,
    WorkoutSessionStart,
    WorkoutSessionStartResponse,
    WorkoutSessionSummary,
    WorkoutSetLogCreate,
    WorkoutSetLogRead,
)
from app.services import feed_service, workout_service

router = APIRouter(prefix="/workout-sessions", tags=["workout-sessions"])


def _load_session(db: Session, session_id: int, user_id: int) -> WorkoutSession:
    session = db.execute(
        select(WorkoutSession)
        .options(selectinload(WorkoutSession.sets).selectinload(WorkoutSetLog.exercise))
        .where(WorkoutSession.id == session_id)
    ).scalar_one_or_none()
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")
    return session


@router.post("", response_model=WorkoutSessionStartResponse, status_code=status.HTTP_201_CREATED)
def start_session(
    payload: WorkoutSessionStart,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    routine = db.execute(
        select(Routine)
        .options(selectinload(Routine.exercises))
        .where(Routine.id == payload.routine_id)
    ).scalar_one_or_none()
    if routine is None or routine.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rotina não encontrada")

    session = WorkoutSession(
        user_id=current_user.id,
        routine_id=routine.id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    prefill = workout_service.build_prefill(db, current_user.id, routine)
    return {"session": session, "prefill": prefill}


@router.post("/{session_id}/sets", response_model=WorkoutSetLogRead, status_code=status.HTTP_201_CREATED)
def log_set(
    session_id: int,
    payload: WorkoutSetLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkoutSetLog:
    session = _load_session(db, session_id, current_user.id)
    if session.completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Essa sessão já foi concluída"
        )

    set_log = WorkoutSetLog(session_id=session.id, **payload.model_dump())
    db.add(set_log)
    db.commit()
    db.refresh(set_log)
    return set_log


@router.post("/{session_id}/complete", response_model=WorkoutSessionSummary)
def complete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    session = _load_session(db, session_id, current_user.id)
    if session.completed_at is None:
        session.completed_at = datetime.now(timezone.utc)
        feed_service.maybe_create_workout_post(db, session)
        db.commit()
        session = _load_session(db, session_id, current_user.id)

    return workout_service.build_summary(db, session)


@router.get("", response_model=list[WorkoutSessionDetail])
def list_sessions(
    routine_id: int | None = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkoutSession]:
    stmt = (
        select(WorkoutSession)
        .options(selectinload(WorkoutSession.sets).selectinload(WorkoutSetLog.exercise))
        .where(WorkoutSession.user_id == current_user.id)
    )
    if routine_id is not None:
        stmt = stmt.where(WorkoutSession.routine_id == routine_id)
    stmt = stmt.order_by(WorkoutSession.started_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())


@router.get("/{session_id}", response_model=WorkoutSessionDetail)
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkoutSession:
    return _load_session(db, session_id, current_user.id)
