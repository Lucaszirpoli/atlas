"""Endpoints de evolução/histórico agregado (espec. seção 3.8) — gráficos
de peso, volume de treino e progressão de carga por exercício. Tudo lido do
histórico append-only, sem nada destrutivo."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.calorie_goal import CalorieGoal
from app.models.exercise import Exercise
from app.models.meal import MealLog, MealLogItem
from app.models.sleep_log import SleepLog
from app.models.user import User
from app.models.water_log import WaterLog
from app.models.weight_log import WeightLog
from app.models.workout_session import WorkoutSession, WorkoutSetLog
from app.schemas.evolution import (
    ConsistencyDay,
    ConsistencyResponse,
    ExerciseOption,
    ExerciseProgressionPoint,
    ExerciseProgressionResponse,
    NutritionDay,
    NutritionHistoryResponse,
    VolumePoint,
    WeightPoint,
)
from app.services import water_service

router = APIRouter(prefix="/evolution", tags=["evolution"])


@router.get("/weight", response_model=list[WeightPoint])
def weight_evolution(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    logs = list(
        db.execute(
            select(WeightLog)
            .where(WeightLog.user_id == current_user.id)
            .order_by(WeightLog.recorded_at)
        ).scalars()
    )
    return [{"date": log.recorded_at, "weight_kg": log.weight_kg} for log in logs]


@router.get("/volume", response_model=list[VolumePoint])
def volume_evolution(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    sessions = list(
        db.execute(
            select(WorkoutSession)
            .where(
                WorkoutSession.user_id == current_user.id,
                WorkoutSession.completed_at.is_not(None),
            )
            .order_by(WorkoutSession.started_at.desc())
            .limit(limit)
        ).scalars()
    )
    sessions.reverse()
    return [
        {
            "date": s.started_at,
            "volume_kg": sum(x.weight_kg * x.reps for x in s.sets),
            "sets": len(s.sets),
        }
        for s in sessions
    ]


@router.get("/exercises", response_model=list[ExerciseOption])
def exercises_with_history(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    """Exercícios que o usuário de fato já executou — para o seletor do
    gráfico de progressão de carga."""
    rows = db.execute(
        select(Exercise.id, Exercise.name, func.count(WorkoutSetLog.id))
        .join(WorkoutSetLog, WorkoutSetLog.exercise_id == Exercise.id)
        .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
        .where(WorkoutSession.user_id == current_user.id)
        .group_by(Exercise.id, Exercise.name)
        .order_by(func.count(WorkoutSetLog.id).desc())
    ).all()
    return [{"id": r[0], "name": r[1], "set_count": r[2]} for r in rows]


@router.get("/exercise/{exercise_id}", response_model=ExerciseProgressionResponse)
def exercise_progression(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Maior carga e volume por sessão para um exercício ao longo do tempo."""
    exercise = db.get(Exercise, exercise_id)
    rows = db.execute(
        select(
            WorkoutSession.started_at,
            func.max(WorkoutSetLog.weight_kg),
            func.sum(WorkoutSetLog.weight_kg * WorkoutSetLog.reps),
        )
        .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
        .where(
            WorkoutSession.user_id == current_user.id,
            WorkoutSetLog.exercise_id == exercise_id,
        )
        .group_by(WorkoutSession.id, WorkoutSession.started_at)
        .order_by(WorkoutSession.started_at)
    ).all()

    points = [
        {"date": r[0], "max_weight_kg": float(r[1] or 0), "volume_kg": float(r[2] or 0)}
        for r in rows
    ]
    return {
        "exercise_name": exercise.name if exercise else "",
        "points": points,
    }


@router.get("/nutrition", response_model=NutritionHistoryResponse)
def nutrition_history(
    days: int = 14,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Total de calorias por dia nos últimos N dias (janela móvel), mais a
    meta calórica atual para calcular adesão — base do módulo Dieta."""
    days = max(1, min(days, 60))
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    since = since.replace(hour=0, minute=0, second=0, microsecond=0)

    meals = db.execute(
        select(MealLog)
        .options(selectinload(MealLog.items))
        .where(MealLog.user_id == current_user.id, MealLog.logged_at >= since)
    ).scalars()

    per_day: dict[str, float] = defaultdict(float)
    for meal in meals:
        key = meal.logged_at.date().isoformat()
        per_day[key] += sum(i.kcal for i in meal.items)

    goal = db.execute(
        select(CalorieGoal)
        .where(CalorieGoal.user_id == current_user.id)
        .order_by(CalorieGoal.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    goal_kcal = goal.kcal if goal else None

    result = []
    for offset in range(days):
        d = (since + timedelta(days=offset)).date()
        key = d.isoformat()
        result.append({"date": d.isoformat(), "kcal": round(per_day.get(key, 0.0))})

    logged_days = [r for r in result if r["kcal"] > 0]
    within = (
        sum(1 for r in logged_days if goal_kcal and r["kcal"] <= goal_kcal * 1.05)
        if goal_kcal
        else 0
    )
    return {
        "days": result,
        "goal_kcal": goal_kcal,
        "days_logged": len(logged_days),
        "days_within_goal": within,
    }


@router.get("/consistency", response_model=ConsistencyResponse)
def consistency(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Visão geral de constância: dos 4 hábitos (treino, sono bom, água na
    meta, dieta registrada), quantos a pessoa cumpriu em cada dia — vira o
    'quão responsável eu tenho sido' com filtro por hábito no app. Tom sempre
    informativo, nunca de culpa (espec. 3.7): um dia sem registro é só isso,
    não uma falha."""
    days = max(7, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    since = since.replace(hour=0, minute=0, second=0, microsecond=0)

    trained_days: set[str] = set()
    sessions = db.execute(
        select(WorkoutSession.completed_at).where(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.completed_at.is_not(None),
            WorkoutSession.completed_at >= since,
        )
    ).scalars()
    for completed_at in sessions:
        trained_days.add(completed_at.date().isoformat())

    slept_well_days: set[str] = set()
    sleep_logs = db.execute(
        select(SleepLog).where(SleepLog.user_id == current_user.id, SleepLog.wake_at >= since)
    ).scalars()
    for log in sleep_logs:
        duration_min = (log.wake_at - log.sleep_at).total_seconds() / 60
        if duration_min >= 7 * 60:
            slept_well_days.add(log.wake_at.date().isoformat())

    water_per_day: dict[str, int] = defaultdict(int)
    water_logs = db.execute(
        select(WaterLog).where(WaterLog.user_id == current_user.id, WaterLog.logged_at >= since)
    ).scalars()
    for log in water_logs:
        water_per_day[log.logged_at.date().isoformat()] += log.amount_ml
    goal_ml = water_service.compute_goal_ml(db, current_user.id)

    logged_food_days: set[str] = set()
    meals = db.execute(
        select(MealLog).where(MealLog.user_id == current_user.id, MealLog.logged_at >= since)
    ).scalars()
    for meal in meals:
        logged_food_days.add(meal.logged_at.date().isoformat())

    result = []
    for offset in range(days):
        d = (since + timedelta(days=offset)).date()
        key = d.isoformat()
        trained = key in trained_days
        slept_well = key in slept_well_days
        hydrated = bool(goal_ml) and water_per_day.get(key, 0) >= goal_ml * 0.9
        logged_food = key in logged_food_days
        habits_done = sum([trained, slept_well, hydrated, logged_food])
        result.append(
            {
                "date": key,
                "trained": trained,
                "slept_well": slept_well,
                "hydrated": hydrated,
                "logged_food": logged_food,
                "score": round(habits_done / 4 * 100),
            }
        )

    # Sequência atual: dias consecutivos (voltando de hoje) com score >= 50
    # (pelo menos 2 dos 4 hábitos). Hoje ainda não "acabou" — se ainda não
    # bateu 50, não quebra a sequência, só não conta ainda (dá tempo).
    today_key = datetime.now(timezone.utc).date().isoformat()
    current_streak = 0
    skipped_today = False
    for r in reversed(result):
        if r["score"] >= 50:
            current_streak += 1
        elif r["date"] == today_key and not skipped_today:
            skipped_today = True
        else:
            break

    best_streak = 0
    running = 0
    for r in result:
        if r["score"] >= 50:
            running += 1
            best_streak = max(best_streak, running)
        else:
            running = 0

    return {
        "days": result,
        "current_streak": current_streak,
        "best_streak": best_streak,
    }
