"""Endpoints de evolução/histórico agregado (espec. seção 3.8) — gráficos
de peso, volume de treino e progressão de carga por exercício. Tudo lido do
histórico append-only, sem nada destrutivo.

FUSO: este arquivo fatiava os dias em UTC (`datetime.now(timezone.utc).date()`)
enquanto o resto do app já fatiava no fuso da PESSOA (app/core/usertime.py).
No Brasil (UTC-3) isso jogava tudo o que era registrado depois das 21h para o
dia seguinte, e fazia o app discordar do calendário do celular sobre que dia é
hoje — o que sujava a grade de constância, a sequência e os rótulos dos
gráficos. Agora todo `.date()` daqui passa por `local_date`/`today_local`.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.usertime import local_date, profile_tz, today_local, window_start_utc
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
    StrengthByGroupResponse,
    VolumePoint,
    WeightPoint,
)
from app.services import water_service

router = APIRouter(prefix="/evolution", tags=["evolution"])


def _tz(user: User) -> ZoneInfo:
    return profile_tz(getattr(user, "profile", None))


def _janela(days: int, tz: ZoneInfo) -> tuple[datetime, date]:
    """(início em UTC, primeiro dia local) da janela dos últimos `days` dias de
    CALENDÁRIO da pessoa — o mesmo recorte que ela vê no celular."""
    return window_start_utc(days, tz), today_local(tz) - timedelta(days=days - 1)


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


# Classificação simples de grupo muscular primário -> superiores/inferiores/
# core, para a análise automática ("sua carga subiu X% nos superiores").
_UPPER = {"chest", "back", "shoulders", "biceps", "triceps", "forearms", "traps"}
_LOWER = {"quads", "hamstrings", "glutes", "calves"}


@router.get("/strength", response_model=StrengthByGroupResponse)
def strength_by_group(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Variação média da carga (maior peso por sessão) no período, agregada
    por grupo de exercícios (superiores/inferiores/core). Cada exercício
    entra com a variação % entre sua primeira e última sessão na janela;
    exercícios com uma sessão só ficam de fora (não têm variação)."""
    days = max(7, min(days, 90))
    since, _ = _janela(days, _tz(current_user))

    rows = db.execute(
        select(
            WorkoutSetLog.exercise_id,
            WorkoutSession.started_at,
            func.max(WorkoutSetLog.weight_kg),
            Exercise.primary_muscle_group,
        )
        .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
        .join(Exercise, Exercise.id == WorkoutSetLog.exercise_id)
        .where(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.started_at >= since,
        )
        .group_by(
            WorkoutSetLog.exercise_id,
            WorkoutSession.id,
            WorkoutSession.started_at,
            Exercise.primary_muscle_group,
        )
        .order_by(WorkoutSession.started_at)
    ).all()

    # por exercício: carga da primeira e da última sessão da janela
    per_exercise: dict[int, dict] = {}
    for exercise_id, _started_at, max_weight, muscle_group in rows:
        if not max_weight or max_weight <= 0:
            continue
        group = muscle_group.value if hasattr(muscle_group, "value") else str(muscle_group)
        rec = per_exercise.setdefault(
            exercise_id, {"group": group, "first": float(max_weight), "last": float(max_weight), "sessions": 0}
        )
        rec["last"] = float(max_weight)  # rows já vêm em ordem cronológica
        rec["sessions"] += 1

    buckets: dict[str, list[float]] = {"superiores": [], "inferiores": [], "core": []}
    for rec in per_exercise.values():
        if rec["sessions"] < 2 or rec["first"] <= 0:
            continue
        pct = (rec["last"] / rec["first"] - 1) * 100
        if rec["group"] in _UPPER:
            buckets["superiores"].append(pct)
        elif rec["group"] in _LOWER:
            buckets["inferiores"].append(pct)
        elif rec["group"] == "abs":
            buckets["core"].append(pct)

    return {
        "groups": [
            {"group": name, "avg_pct_change": sum(v) / len(v), "exercises_count": len(v)}
            for name, v in buckets.items()
            if v
        ]
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
    tz = _tz(current_user)
    since, primeiro_dia = _janela(days, tz)

    meals = db.execute(
        select(MealLog)
        .options(selectinload(MealLog.items))
        .where(MealLog.user_id == current_user.id, MealLog.logged_at >= since)
    ).scalars()

    per_day: dict[str, float] = defaultdict(float)
    prot_day: dict[str, float] = defaultdict(float)
    carb_day: dict[str, float] = defaultdict(float)
    fat_day: dict[str, float] = defaultdict(float)
    for meal in meals:
        key = local_date(meal.logged_at, tz).isoformat()
        per_day[key] += sum(i.kcal for i in meal.items)
        prot_day[key] += sum(i.protein_g for i in meal.items)
        carb_day[key] += sum(i.carbs_g for i in meal.items)
        fat_day[key] += sum(i.fat_g for i in meal.items)

    goal = db.execute(
        select(CalorieGoal)
        .where(CalorieGoal.user_id == current_user.id)
        .order_by(CalorieGoal.created_at.desc(), CalorieGoal.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    goal_kcal = goal.kcal if goal else None

    result = []
    for offset in range(days):
        d = primeiro_dia + timedelta(days=offset)
        key = d.isoformat()
        result.append({
            "date": d.isoformat(),
            "kcal": round(per_day.get(key, 0.0)),
            "protein_g": round(prot_day.get(key, 0.0), 1),
            "carbs_g": round(carb_day.get(key, 0.0), 1),
            "fat_g": round(fat_day.get(key, 0.0), 1),
        })

    logged_days = [r for r in result if r["kcal"] > 0]
    within = (
        sum(1 for r in logged_days if goal_kcal and r["kcal"] <= goal_kcal * 1.05)
        if goal_kcal
        else 0
    )
    return {
        "days": result,
        "goal_kcal": goal_kcal,
        "goal_protein_g": goal.protein_g if goal else None,
        "goal_carbs_g": goal.carbs_g if goal else None,
        "goal_fat_g": goal.fat_g if goal else None,
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
    não uma falha.

    A SEQUÊNCIA (e o recorde) contam DIA ATIVO, não "2 dos 4 hábitos". Exigir
    metade dos hábitos fazia a sequência ficar parada em zero pra quem usa o app
    todo dia mas não fecha os quatro — a pessoa registrava o almoço, o app dizia
    "0 dias seguidos", e o número que existe pra dar constância virava punição.
    Qualquer registro do dia (treino, comida, água ou sono) mantém a sequência
    viva; os hábitos continuam aparecendo um a um na grade."""
    days = max(7, min(days, 90))
    tz = _tz(current_user)
    since, primeiro_dia = _janela(days, tz)

    trained_days: set[str] = set()
    sessions = db.execute(
        select(WorkoutSession.completed_at).where(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.completed_at.is_not(None),
            WorkoutSession.completed_at >= since,
        )
    ).scalars()
    for completed_at in sessions:
        trained_days.add(local_date(completed_at, tz).isoformat())

    slept_well_days: set[str] = set()
    slept_days: set[str] = set()
    sleep_logs = db.execute(
        select(SleepLog).where(SleepLog.user_id == current_user.id, SleepLog.wake_at >= since)
    ).scalars()
    for log in sleep_logs:
        key = local_date(log.wake_at, tz).isoformat()
        slept_days.add(key)
        duration_min = (log.wake_at - log.sleep_at).total_seconds() / 60
        if duration_min >= 7 * 60:
            slept_well_days.add(key)

    water_per_day: dict[str, int] = defaultdict(int)
    water_logs = db.execute(
        select(WaterLog).where(WaterLog.user_id == current_user.id, WaterLog.logged_at >= since)
    ).scalars()
    for log in water_logs:
        water_per_day[local_date(log.logged_at, tz).isoformat()] += log.amount_ml
    goal_ml = water_service.compute_goal_ml(db, current_user.id)

    logged_food_days: set[str] = set()
    meals = db.execute(
        select(MealLog).where(MealLog.user_id == current_user.id, MealLog.logged_at >= since)
    ).scalars()
    for meal in meals:
        logged_food_days.add(local_date(meal.logged_at, tz).isoformat())

    # Peso também conta como "usei o app hoje" — pesar-se é registro.
    weighed_days: set[str] = set()
    for recorded_at in db.execute(
        select(WeightLog.recorded_at).where(
            WeightLog.user_id == current_user.id, WeightLog.recorded_at >= since
        )
    ).scalars():
        weighed_days.add(local_date(recorded_at, tz).isoformat())

    result = []
    for offset in range(days):
        d = primeiro_dia + timedelta(days=offset)
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
                "active": bool(
                    trained
                    or logged_food
                    or key in slept_days
                    or key in weighed_days
                    or water_per_day.get(key, 0) > 0
                ),
                "score": round(habits_done / 4 * 100),
            }
        )

    current_streak, best_streak = compute_streaks(result, today_local(tz).isoformat())
    return {
        "days": result,
        "current_streak": current_streak,
        "best_streak": best_streak,
    }


def compute_streaks(days: list[dict], hoje: str) -> tuple[int, int]:
    """(sequência atual, recorde) a partir dos dias em ordem cronológica.

    Duas regras que existem pra proteger a pessoa, não o número:
    - HOJE ainda não acabou. Se ela ainda não registrou nada hoje, isso não
      quebra a sequência — ela tem o dia inteiro pra abrir o app.
    - o recorde nunca fica ABAIXO da sequência atual: a janela é de 90 dias, e
      uma sequência que começou antes dela apareceria cortada pela metade.
    """
    atual = 0
    for r in reversed(days):
        if r["active"]:
            atual += 1
        elif r["date"] == hoje:
            continue
        else:
            break

    recorde = 0
    corrida = 0
    for r in days:
        if r["active"]:
            corrida += 1
            recorde = max(recorde, corrida)
        else:
            corrida = 0
    return atual, max(recorde, atual)
