"""Placar dos desafios. Toda métrica é calculada em runtime a partir do
histórico REAL da pessoa no período — nunca um contador incrementado à mão
(assim ninguém "digita" pontos e o placar sempre reflete o que aconteceu).

Os tipos cobrem os 4 módulos do app: treino, consistência, saúde (sono/água) e
dieta. Nenhum tipo premia restrição ou perda de peso — decisão de produto
(espec. 3.7, saúde mental): desafio de "quem emagrece mais" incentiva
comportamento perigoso, então não existe aqui.
"""

from collections import defaultdict
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.challenge import Challenge, ChallengeMetric, ChallengeParticipant
from app.models.gym import GymCheckIn
from app.models.meal import MealLog, MealLogItem
from app.models.sleep_log import SleepLog
from app.models.water_log import WaterLog
from app.models.workout_session import SetType, WorkoutSession
from app.services import goal_service, water_service, workout_service

# Séries que NÃO contam como carga levantada: aquecimento e preparatória são
# preparação, não trabalho. O resto (válida, drop-set, rest-pause, falha etc.)
# conta.
NON_WORKING_SET_TYPES = {SetType.WARMUP, SetType.FEEDER}

# Uma noite "bem dormida" no desafio de sono.
GOOD_SLEEP_MINUTES = 7 * 60


def _period_bounds(challenge: Challenge) -> tuple[datetime, datetime]:
    start = datetime.combine(challenge.start_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(challenge.end_date, time.max, tzinfo=timezone.utc)
    return start, end


def _sessions_in_period(db: Session, user_id: int, challenge: Challenge) -> list[WorkoutSession]:
    start, end = _period_bounds(challenge)
    return list(
        db.execute(
            select(WorkoutSession).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.completed_at.is_not(None),
                WorkoutSession.started_at >= start,
                WorkoutSession.started_at <= end,
            )
        ).scalars()
    )


def _longest_streak(sessions: list[WorkoutSession]) -> int:
    days = sorted({s.started_at.date() for s in sessions})
    if not days:
        return 0
    longest = current = 1
    for prev, curr in zip(days, days[1:]):
        if (curr - prev).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _working_volume(sessions: list[WorkoutSession]) -> float:
    """Carga total = peso × reps, SÓ das séries válidas (sem aquecimento nem
    preparatória) — senão quem faz muito aquecimento leve "ganharia" volume."""
    return sum(
        s.weight_kg * s.reps
        for session in sessions
        for s in session.sets
        if s.set_type not in NON_WORKING_SET_TYPES
    )


def _pr_count(db: Session, sessions: list[WorkoutSession]) -> int:
    """Quantos recordes pessoais a pessoa bateu no período (usa a mesma
    detecção do resumo de treino: compara com todo o histórico anterior)."""
    total = 0
    for session in sessions:
        try:
            total += len(workout_service.detect_prs(db, session))
        except Exception:
            continue
    return total


def _good_sleep_nights(db: Session, user_id: int, challenge: Challenge) -> int:
    start, end = _period_bounds(challenge)
    logs = list(
        db.execute(
            select(SleepLog).where(
                SleepLog.user_id == user_id,
                SleepLog.sleep_at >= start,
                SleepLog.sleep_at <= end,
            )
        ).scalars()
    )
    return sum(
        1
        for l in logs
        if l.wake_at and l.sleep_at and (l.wake_at - l.sleep_at).total_seconds() / 60 >= GOOD_SLEEP_MINUTES
    )


def _days_hitting_water_goal(db: Session, user_id: int, challenge: Challenge) -> int:
    goal_ml = water_service.compute_goal_ml(db, user_id)
    if not goal_ml:
        return 0
    start, end = _period_bounds(challenge)
    logs = list(
        db.execute(
            select(WaterLog).where(
                WaterLog.user_id == user_id,
                WaterLog.logged_at >= start,
                WaterLog.logged_at <= end,
            )
        ).scalars()
    )
    per_day: dict[date, float] = defaultdict(float)
    for l in logs:
        per_day[l.logged_at.date()] += l.amount_ml
    return sum(1 for total in per_day.values() if total >= goal_ml)


def _meal_totals_per_day(db: Session, user_id: int, challenge: Challenge) -> dict[date, dict[str, float]]:
    start, end = _period_bounds(challenge)
    meals = list(
        db.execute(
            select(MealLog).where(
                MealLog.user_id == user_id,
                MealLog.logged_at >= start,
                MealLog.logged_at <= end,
            )
        ).scalars()
    )
    per_day: dict[date, dict[str, float]] = defaultdict(lambda: {"kcal": 0.0, "protein_g": 0.0})
    for meal in meals:
        items = list(
            db.execute(select(MealLogItem).where(MealLogItem.meal_log_id == meal.id)).scalars()
        )
        day = meal.logged_at.date()
        for it in items:
            per_day[day]["kcal"] += it.kcal
            per_day[day]["protein_g"] += it.protein_g
    return per_day


def _days_hitting_protein_goal(db: Session, user_id: int, challenge: Challenge) -> int:
    goal = goal_service.get_current_goal(db, user_id)
    if goal is None or not goal.protein_g:
        return 0
    per_day = _meal_totals_per_day(db, user_id, challenge)
    return sum(1 for totals in per_day.values() if totals["protein_g"] >= goal.protein_g)


def _days_with_diet_logged(db: Session, user_id: int, challenge: Challenge) -> int:
    return len(_meal_totals_per_day(db, user_id, challenge))


def _gym_checkins_in_period(db: Session, user_id: int, challenge: Challenge) -> int:
    """Check-ins com prova de localização. Conta também os feitos fora da
    academia cadastrada (marcados "fora") — quem viajou não perde o dia."""
    return len(
        list(
            db.execute(
                select(GymCheckIn).where(
                    GymCheckIn.user_id == user_id,
                    GymCheckIn.day >= challenge.start_date,
                    GymCheckIn.day <= challenge.end_date,
                )
            ).scalars()
        )
    )


def compute_metric_value(db: Session, user_id: int, challenge: Challenge) -> float:
    m = challenge.metric

    # Métricas que não dependem de sessão de treino
    if m == ChallengeMetric.GYM_CHECKIN:
        return float(_gym_checkins_in_period(db, user_id, challenge))
    if m == ChallengeMetric.SLEEP_NIGHTS:
        return float(_good_sleep_nights(db, user_id, challenge))
    if m == ChallengeMetric.WATER_GOAL_DAYS:
        return float(_days_hitting_water_goal(db, user_id, challenge))
    if m == ChallengeMetric.PROTEIN_GOAL_DAYS:
        return float(_days_hitting_protein_goal(db, user_id, challenge))
    if m == ChallengeMetric.DIET_LOGGED_DAYS:
        return float(_days_with_diet_logged(db, user_id, challenge))

    sessions = _sessions_in_period(db, user_id, challenge)
    if m == ChallengeMetric.WORKOUT_COUNT:
        return float(len(sessions))
    if m == ChallengeMetric.TOTAL_VOLUME:
        return _working_volume(sessions)
    if m == ChallengeMetric.STREAK_DAYS:
        return float(_longest_streak(sessions))
    if m == ChallengeMetric.PR_COUNT:
        return float(_pr_count(db, sessions))
    return 0.0


def build_leaderboard(db: Session, challenge: Challenge) -> list[dict]:
    participants = list(
        db.execute(
            select(ChallengeParticipant).where(ChallengeParticipant.challenge_id == challenge.id)
        ).scalars()
    )
    entries = [
        {"user_id": p.user_id, "value": compute_metric_value(db, p.user_id, challenge)}
        for p in participants
    ]
    entries.sort(key=lambda e: e["value"], reverse=True)
    return entries
