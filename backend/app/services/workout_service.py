from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.routine import Routine
from app.models.workout_session import WorkoutSession, WorkoutSetLog


def get_last_performance(db: Session, user_id: int, exercise_id: int) -> dict | None:
    """Última vez que o usuário executou esse exercício, em qualquer rotina —
    usado para pré-preencher peso/reps na tela de execução."""
    last_session_id = db.execute(
        select(WorkoutSetLog.session_id)
        .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
        .where(WorkoutSession.user_id == user_id, WorkoutSetLog.exercise_id == exercise_id)
        .order_by(WorkoutSession.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if last_session_id is None:
        return None

    session = db.get(WorkoutSession, last_session_id)
    sets = list(
        db.execute(
            select(WorkoutSetLog)
            .where(
                WorkoutSetLog.session_id == last_session_id,
                WorkoutSetLog.exercise_id == exercise_id,
            )
            .order_by(WorkoutSetLog.set_number)
        ).scalars()
    )
    return {
        "exercise_id": exercise_id,
        "last_performed_at": session.started_at,
        "sets": [
            {"set_number": s.set_number, "weight_kg": s.weight_kg, "reps": s.reps} for s in sets
        ],
    }


def build_prefill(db: Session, user_id: int, routine: Routine) -> list[dict]:
    prefill = []
    for routine_exercise in routine.exercises:
        performance = get_last_performance(db, user_id, routine_exercise.exercise_id)
        prefill.append(
            performance
            or {"exercise_id": routine_exercise.exercise_id, "last_performed_at": None, "sets": []}
        )
    return prefill


def compute_session_volume(session: WorkoutSession) -> float:
    return sum(s.weight_kg * s.reps for s in session.sets)


def get_previous_completed_session(
    db: Session, user_id: int, routine_id: int | None, before_session_id: int
) -> WorkoutSession | None:
    return db.execute(
        select(WorkoutSession)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.routine_id == routine_id,
            WorkoutSession.id != before_session_id,
            WorkoutSession.completed_at.is_not(None),
        )
        .order_by(WorkoutSession.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def detect_prs(db: Session, session: WorkoutSession) -> list[dict]:
    """PR = maior peso já levantado num exercício, batido nesta sessão
    (espec. 3.3/3.8: 'recordes pessoais destacados automaticamente')."""
    exercise_ids = {s.exercise_id for s in session.sets}
    prs = []
    for exercise_id in exercise_ids:
        session_max = max(s.weight_kg for s in session.sets if s.exercise_id == exercise_id)

        prior_max = db.execute(
            select(func.max(WorkoutSetLog.weight_kg))
            .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
            .where(
                WorkoutSession.user_id == session.user_id,
                WorkoutSetLog.exercise_id == exercise_id,
                WorkoutSession.id != session.id,
                WorkoutSession.completed_at.is_not(None),
            )
        ).scalar_one_or_none()

        if prior_max is None or session_max > prior_max:
            exercise = db.get(Exercise, exercise_id)
            prs.append(
                {
                    "exercise_id": exercise_id,
                    "exercise_name": exercise.name if exercise else "",
                    "weight_kg": session_max,
                }
            )
    return prs


def build_summary(db: Session, session: WorkoutSession) -> dict:
    total_volume = compute_session_volume(session)
    duration = (
        int((session.completed_at - session.started_at).total_seconds())
        if session.completed_at
        else 0
    )

    previous = get_previous_completed_session(db, session.user_id, session.routine_id, session.id)
    previous_volume = compute_session_volume(previous) if previous else None
    change_percent = (
        ((total_volume - previous_volume) / previous_volume * 100)
        if previous_volume
        else None
    )

    return {
        "session": session,
        "total_volume_kg": total_volume,
        "duration_seconds": duration,
        "previous_session_volume_kg": previous_volume,
        "volume_change_percent": round(change_percent, 1) if change_percent is not None else None,
        "prs": detect_prs(db, session),
    }
