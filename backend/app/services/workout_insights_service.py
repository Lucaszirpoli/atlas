"""Detecção de platô e sugestão de deload (espec. 3.3: '[GAP] Detecção de
platô... [GAP] Semana de deload automática sugerida a cada 4-8 semanas'),
listada como recurso do plano Pro na Parte 4. A análise em si é
determinística (não chama a IA generativa) — é a apresentação como parte do
"AI Coach" que é exclusiva do Pro, por decisão de modelo de negócio."""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.workout_session import WorkoutSession, WorkoutSetLog

PLATEAU_SESSION_WINDOW = 3
DELOAD_CONSECUTIVE_WEEKS_THRESHOLD = 4


def _completed_sessions(db: Session, user_id: int) -> list[WorkoutSession]:
    return list(
        db.execute(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user_id, WorkoutSession.completed_at.is_not(None))
            .order_by(WorkoutSession.started_at)
        ).scalars()
    )


def detect_plateaus(db: Session, user_id: int) -> list[dict]:
    sessions = _completed_sessions(db, user_id)

    max_weight_by_exercise_per_session: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for session in sessions:
        per_exercise_max: dict[int, float] = defaultdict(float)
        for s in session.sets:
            per_exercise_max[s.exercise_id] = max(per_exercise_max[s.exercise_id], s.weight_kg)
        for exercise_id, weight in per_exercise_max.items():
            max_weight_by_exercise_per_session[exercise_id].append((session.started_at.date(), weight))

    plateaus = []
    for exercise_id, history in max_weight_by_exercise_per_session.items():
        if len(history) < PLATEAU_SESSION_WINDOW:
            continue
        recent = history[-PLATEAU_SESSION_WINDOW:]
        weights = [w for _, w in recent]
        if max(weights) <= weights[0]:
            exercise = db.get(Exercise, exercise_id)
            plateaus.append(
                {
                    "exercise_id": exercise_id,
                    "exercise_name": exercise.name if exercise else "",
                    "sessions_without_progress": PLATEAU_SESSION_WINDOW,
                    "current_weight_kg": weights[-1],
                }
            )
    return plateaus


def detect_deload_suggestion(db: Session, user_id: int) -> dict:
    sessions = _completed_sessions(db, user_id)
    trained_weeks = {s.started_at.date().isocalendar()[:2] for s in sessions}

    today = date.today()
    consecutive_weeks = 0
    cursor = today
    while cursor.isocalendar()[:2] in trained_weeks:
        consecutive_weeks += 1
        cursor -= timedelta(weeks=1)

    suggested = consecutive_weeks >= DELOAD_CONSECUTIVE_WEEKS_THRESHOLD
    return {
        "consecutive_weeks_trained": consecutive_weeks,
        "suggested": suggested,
        "message": (
            f"Você treina há {consecutive_weeks} semanas seguidas sem parar. "
            "Considere uma semana de deload (volume/intensidade reduzidos) para "
            "recuperar e continuar progredindo."
            if suggested
            else "Nada indica necessidade de deload agora."
        ),
    }
