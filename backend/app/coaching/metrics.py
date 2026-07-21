"""Camada 1 — MÉTRICAS. Lê o histórico append-only (peso, refeições, sessões,
sono) e destila números objetivos. Sem julgamento aqui: só medir. As camadas de
detecção/diagnóstico é que interpretam.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.calorie_goal import CalorieGoal
from app.models.exercise import Exercise
from app.models.meal import MealLog
from app.models.sleep_log import SleepLog
from app.models.user_profile import UserProfile
from app.models.weight_log import WeightLog
from app.models.workout_session import WorkoutSession, WorkoutSetLog


@dataclass
class WeightMetrics:
    latest_kg: float | None
    trend_kg_per_week: float | None  # inclinação da regressão × 7
    pct_bodyweight_per_week: float | None
    points: int
    span_days: int


@dataclass
class NutritionMetrics:
    goal_kcal: float | None
    goal_protein_g: float | None
    avg_kcal_logged: float | None  # média nos dias COM registro
    avg_protein_logged: float | None
    days_logged: int
    window_days: int


@dataclass
class TrainingMetrics:
    sessions: int
    sessions_per_week: float
    window_days: int
    # Exercícios principais que pararam de progredir na janela.
    # Cada item: {"name": str, "sessions": int, "span_days": int}
    stalled_lifts: list[dict]


@dataclass
class SleepMetrics:
    avg_hours: float | None
    avg_quality: float | None
    nights: int


@dataclass
class Metrics:
    window_days: int
    goal: str | None
    weight_kg: float | None  # peso atual, base dos cálculos por kg
    weight: WeightMetrics
    nutrition: NutritionMetrics
    training: TrainingMetrics
    sleep: SleepMetrics


def _linreg_slope(xs: list[float], ys: list[float]) -> float | None:
    """Inclinação por mínimos quadrados (unidade de y por unidade de x).
    None quando não há variação suficiente em x."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / sxx


def _weight_metrics(db: Session, user_id: int, since: datetime) -> tuple[WeightMetrics, float | None]:
    logs = list(
        db.execute(
            select(WeightLog)
            .where(WeightLog.user_id == user_id, WeightLog.recorded_at >= since)
            .order_by(WeightLog.recorded_at)
        ).scalars()
    )
    # Peso atual = registro mais recente (mesmo fora da janela), pra cálculos /kg.
    latest_any = db.execute(
        select(WeightLog.weight_kg)
        .where(WeightLog.user_id == user_id)
        .order_by(WeightLog.recorded_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if len(logs) < 2:
        latest = logs[-1].weight_kg if logs else latest_any
        return WeightMetrics(latest_kg=latest, trend_kg_per_week=None,
                             pct_bodyweight_per_week=None, points=len(logs), span_days=0), latest_any

    t0 = logs[0].recorded_at
    xs = [(lg.recorded_at - t0).total_seconds() / 86400.0 for lg in logs]  # dias
    ys = [lg.weight_kg for lg in logs]
    span_days = int(round(xs[-1]))
    slope_per_day = _linreg_slope(xs, ys)
    latest = logs[-1].weight_kg
    trend_week = round(slope_per_day * 7, 3) if slope_per_day is not None else None
    pct = round(trend_week / latest * 100, 3) if trend_week is not None and latest else None
    return WeightMetrics(latest_kg=latest, trend_kg_per_week=trend_week,
                         pct_bodyweight_per_week=pct, points=len(logs), span_days=span_days), latest_any


def _nutrition_metrics(db: Session, user_id: int, since: datetime, window_days: int) -> NutritionMetrics:
    meals = db.execute(
        select(MealLog)
        .options(selectinload(MealLog.items))
        .where(MealLog.user_id == user_id, MealLog.logged_at >= since)
    ).scalars()

    kcal_by_day: dict[str, float] = defaultdict(float)
    prot_by_day: dict[str, float] = defaultdict(float)
    for meal in meals:
        key = meal.logged_at.date().isoformat()
        kcal_by_day[key] += sum(i.kcal for i in meal.items)
        prot_by_day[key] += sum(i.protein_g for i in meal.items)

    days_logged = len(kcal_by_day)
    avg_kcal = round(sum(kcal_by_day.values()) / days_logged) if days_logged else None
    avg_prot = round(sum(prot_by_day.values()) / days_logged, 1) if days_logged else None

    goal = db.execute(
        select(CalorieGoal)
        .where(CalorieGoal.user_id == user_id)
        .order_by(CalorieGoal.created_at.desc(), CalorieGoal.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    return NutritionMetrics(
        goal_kcal=goal.kcal if goal else None,
        goal_protein_g=goal.protein_g if goal else None,
        avg_kcal_logged=avg_kcal,
        avg_protein_logged=avg_prot,
        days_logged=days_logged,
        window_days=window_days,
    )


def _e1rm(weight_kg: float, reps: int) -> float:
    """1RM estimado (Epley) — capta progresso por carga OU por reps, então uma
    série de 80×8 e outra de 80×10 não parecem 'iguais'."""
    return weight_kg * (1 + reps / 30.0)


def _stalled_lifts(db: Session, user_id: int, since: datetime) -> list[dict]:
    """Exercícios principais que não progrediram: pra cada exercício treinado em
    ≥3 sessões num intervalo ≥14 dias, compara o melhor e1RM da metade recente
    com o da metade inicial. Sem ganho (dentro de 1%) = travado. Prioriza
    compostos e os mais treinados; devolve no máximo 2 (não assusta a pessoa)."""
    rows = db.execute(
        select(
            WorkoutSetLog.exercise_id,
            Exercise.name,
            Exercise.is_compound,
            WorkoutSession.started_at,
            WorkoutSetLog.weight_kg,
            WorkoutSetLog.reps,
        )
        .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
        .join(Exercise, Exercise.id == WorkoutSetLog.exercise_id)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.started_at >= since,
            WorkoutSession.completed_at.is_not(None),
            WorkoutSetLog.weight_kg > 0,
            WorkoutSetLog.reps > 0,
        )
    ).all()

    # exercise_id -> {name, is_compound, per_session: {day -> best_e1rm}}
    by_ex: dict[int, dict] = {}
    for ex_id, name, is_comp, started_at, w, reps in rows:
        d = by_ex.setdefault(ex_id, {"name": name, "is_compound": bool(is_comp), "sessions": {}})
        day = started_at.date().isoformat()
        e = _e1rm(w, reps)
        if e > d["sessions"].get(day, 0):
            d["sessions"][day] = e

    stalled: list[dict] = []
    for ex_id, d in by_ex.items():
        dias = sorted(d["sessions"].items())  # [(day, best_e1rm)], cronológico
        if len(dias) < 3:
            continue
        span = (datetime.fromisoformat(dias[-1][0]) - datetime.fromisoformat(dias[0][0])).days
        if span < 14:
            continue
        meio = len(dias) // 2
        melhor_inicio = max(e for _, e in dias[:meio] or dias[:1])
        melhor_recente = max(e for _, e in dias[meio:])
        if melhor_recente <= melhor_inicio * 1.01:  # não subiu de forma relevante
            stalled.append(
                {"name": d["name"], "sessions": len(dias), "span_days": span, "is_compound": d["is_compound"]}
            )

    # compostos primeiro, depois os mais treinados
    stalled.sort(key=lambda s: (not s["is_compound"], -s["sessions"]))
    return [{"name": s["name"], "sessions": s["sessions"], "span_days": s["span_days"]} for s in stalled[:2]]


def _training_metrics(db: Session, user_id: int, since: datetime, window_days: int) -> TrainingMetrics:
    # Só sessões CONCLUÍDAS contam como treino feito.
    sessions = db.execute(
        select(WorkoutSession.started_at)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.started_at >= since,
            WorkoutSession.completed_at.is_not(None),
        )
    ).scalars().all()
    n = len(sessions)
    weeks = max(window_days / 7.0, 1.0)
    return TrainingMetrics(
        sessions=n,
        sessions_per_week=round(n / weeks, 2),
        window_days=window_days,
        stalled_lifts=_stalled_lifts(db, user_id, since),
    )


def _sleep_metrics(db: Session, user_id: int, since: datetime) -> SleepMetrics:
    logs = list(
        db.execute(
            select(SleepLog).where(SleepLog.user_id == user_id, SleepLog.sleep_at >= since)
        ).scalars()
    )
    if not logs:
        return SleepMetrics(avg_hours=None, avg_quality=None, nights=0)
    hours = [(lg.wake_at - lg.sleep_at).total_seconds() / 3600.0 for lg in logs]
    hours = [h for h in hours if 0 < h < 24]  # descarta registro incoerente
    avg_h = round(sum(hours) / len(hours), 1) if hours else None
    avg_q = round(sum(lg.quality for lg in logs) / len(logs), 1)
    return SleepMetrics(avg_hours=avg_h, avg_quality=avg_q, nights=len(logs))


def compute_metrics(db: Session, user_id: int, window_days: int = 28, *, now: datetime | None = None) -> Metrics:
    """Destila as métricas da janela (padrão 4 semanas). `now` é injetável só
    pra teste — em produção usa o relógio."""
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=window_days)).replace(hour=0, minute=0, second=0, microsecond=0)

    profile = db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    ).scalar_one_or_none()
    goal = profile.goal.value if profile else None

    weight, latest_any = _weight_metrics(db, user_id, since)
    return Metrics(
        window_days=window_days,
        goal=goal,
        weight_kg=weight.latest_kg or latest_any,
        weight=weight,
        nutrition=_nutrition_metrics(db, user_id, since, window_days),
        training=_training_metrics(db, user_id, since, window_days),
        sleep=_sleep_metrics(db, user_id, since),
    )
