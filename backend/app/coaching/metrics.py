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
from app.models.coaching_baseline import CoachingBaseline
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
    goal_carbs_g: float | None
    goal_fat_g: float | None
    avg_kcal_logged: float | None  # média nos dias COM registro
    avg_protein_logged: float | None
    avg_carbs_logged: float | None
    avg_fat_logged: float | None
    days_logged: int
    window_days: int


@dataclass
class TrainingMetrics:
    sessions: int
    sessions_per_week: float
    window_days: int
    # Exercícios principais que pararam de progredir na janela.
    # Cada item: {"exercise_id": int, "name": str, "sessions": int,
    #             "span_days": int, "is_compound": bool}
    stalled_lifts: list[dict]
    # Exercícios em que a pessoa está PRONTA pra subir a carga (bateu o topo da
    # faixa de reps com folga). Cada item: {"exercise_id", "name", "is_compound",
    #   "muscle", "equipment", "top_weight", "top_reps", "sessions"}
    progression_lifts: list[dict]
    # Tendência da carga total (volume = Σ peso×reps por sessão): % da metade
    # recente vs a inicial. Positivo = subindo. None = poucos treinos.
    volume_trend_pct: float | None


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
    # Preenchido quando um marco de recomeço (troca de objetivo) está DENTRO da
    # janela e recortou a leitura — a UI usa pra explicar por que o período é
    # menor. None = sem marco ativo afetando a janela.
    baseline_at: datetime | None = None


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
    carb_by_day: dict[str, float] = defaultdict(float)
    fat_by_day: dict[str, float] = defaultdict(float)
    for meal in meals:
        key = meal.logged_at.date().isoformat()
        kcal_by_day[key] += sum(i.kcal for i in meal.items)
        prot_by_day[key] += sum(i.protein_g for i in meal.items)
        carb_by_day[key] += sum(i.carbs_g for i in meal.items)
        fat_by_day[key] += sum(i.fat_g for i in meal.items)

    days_logged = len(kcal_by_day)

    def _avg(d: dict[str, float], nd: int = 0) -> float | None:
        return round(sum(d.values()) / days_logged, nd) if days_logged else None

    goal = db.execute(
        select(CalorieGoal)
        .where(CalorieGoal.user_id == user_id)
        .order_by(CalorieGoal.created_at.desc(), CalorieGoal.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    return NutritionMetrics(
        goal_kcal=goal.kcal if goal else None,
        goal_protein_g=goal.protein_g if goal else None,
        goal_carbs_g=goal.carbs_g if goal else None,
        goal_fat_g=goal.fat_g if goal else None,
        avg_kcal_logged=None if _avg(kcal_by_day) is None else round(sum(kcal_by_day.values()) / days_logged),
        avg_protein_logged=_avg(prot_by_day, 1),
        avg_carbs_logged=_avg(carb_by_day, 1),
        avg_fat_logged=_avg(fat_by_day, 1),
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
                {"exercise_id": ex_id, "name": d["name"], "sessions": len(dias),
                 "span_days": span, "is_compound": d["is_compound"]}
            )

    # compostos primeiro, depois os mais treinados
    stalled.sort(key=lambda s: (not s["is_compound"], -s["sessions"]))
    return [
        {"exercise_id": s["exercise_id"], "name": s["name"], "sessions": s["sessions"],
         "span_days": s["span_days"], "is_compound": s["is_compound"]}
        for s in stalled[:2]
    ]


# Reps que marcam o topo de uma boa faixa de trabalho — bateu isto com folga,
# está na hora de subir a carga. Peso corporal aguenta mais reps antes do sinal.
_PROG_REP_CEIL_WEIGHTED = 12
_PROG_REP_CEIL_BODYWEIGHT = 18
# set_types que NÃO são série de trabalho (não valem pro sinal de progressão).
_NON_WORKING_SETS = {"warmup", "feeder"}


def _progression_lifts(db: Session, user_id: int, since: datetime, stalled_ids: set[int]) -> list[dict]:
    """Exercícios prontos pra subir a carga: no treino mais recente a pessoa
    bateu o TOPO da faixa de reps na série mais pesada, com folga (RIR ≥ 1 ou não
    informado). É o oposto do platô — por isso exclui quem já está travado. Sinal
    de coach de verdade: 'você tá voando nesse peso, sobe'.

    Devolve no máximo 3, compostos primeiro (subir num composto rende mais)."""
    from app.models.exercise import Equipment

    rows = db.execute(
        select(
            WorkoutSetLog.exercise_id,
            Exercise.name,
            Exercise.is_compound,
            Exercise.primary_muscle_group,
            Exercise.equipment,
            WorkoutSession.started_at,
            WorkoutSetLog.weight_kg,
            WorkoutSetLog.reps,
            WorkoutSetLog.rir,
            WorkoutSetLog.set_type,
        )
        .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
        .join(Exercise, Exercise.id == WorkoutSetLog.exercise_id)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.started_at >= since,
            WorkoutSession.completed_at.is_not(None),
            WorkoutSetLog.reps > 0,
        )
    ).all()

    # exercise_id -> {meta, days: {day -> (peso, reps, rir) da série de trabalho mais pesada}}
    by_ex: dict[int, dict] = {}
    for ex_id, name, is_comp, muscle, equip, started_at, w, reps, rir, stype in rows:
        st = stype.value if hasattr(stype, "value") else str(stype)
        if st in _NON_WORKING_SETS:
            continue
        d = by_ex.setdefault(ex_id, {
            "name": name, "is_compound": bool(is_comp),
            "muscle": muscle.value if hasattr(muscle, "value") else str(muscle),
            "equipment": equip.value if hasattr(equip, "value") else str(equip),
            "days": {},
        })
        day = started_at.date().isoformat()
        cur = d["days"].get(day)
        # série de trabalho mais pesada do dia (empate: mais reps)
        if cur is None or (w or 0, reps) > (cur[0], cur[1]):
            d["days"][day] = (w or 0.0, reps, rir)

    out: list[dict] = []
    for ex_id, d in by_ex.items():
        if ex_id in stalled_ids:
            continue
        dias = sorted(d["days"].items())  # cronológico
        if len(dias) < 2:
            continue
        _, (peso, reps, rir) = dias[-1]  # treino mais recente
        is_bw = d["equipment"] == Equipment.BODYWEIGHT.value
        teto = _PROG_REP_CEIL_BODYWEIGHT if is_bw else _PROG_REP_CEIL_WEIGHTED
        folga = rir is None or rir >= 1
        if reps >= teto and folga and (is_bw or peso > 0):
            out.append({
                "exercise_id": ex_id, "name": d["name"], "is_compound": d["is_compound"],
                "muscle": d["muscle"], "equipment": d["equipment"],
                "top_weight": round(peso, 1), "top_reps": reps, "sessions": len(dias),
            })

    out.sort(key=lambda s: (not s["is_compound"], -s["top_reps"]))
    return out[:3]


def _volume_trend(db: Session, user_id: int, since: datetime) -> float | None:
    """Carga: volume total (Σ peso×reps) por sessão, tendência recente vs inicial.
    Precisa de ≥4 sessões pra comparar duas metades com sentido."""
    rows = db.execute(
        select(WorkoutSession.started_at, WorkoutSetLog.weight_kg, WorkoutSetLog.reps)
        .join(WorkoutSetLog, WorkoutSetLog.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.started_at >= since,
            WorkoutSession.completed_at.is_not(None),
        )
    ).all()
    vol_by_session: dict[str, float] = defaultdict(float)
    for started_at, w, reps in rows:
        vol_by_session[started_at.isoformat()] += (w or 0) * (reps or 0)
    vols = [v for _, v in sorted(vol_by_session.items())]
    if len(vols) < 4:
        return None
    meio = len(vols) // 2
    ini = sum(vols[:meio]) / meio
    rec = sum(vols[meio:]) / (len(vols) - meio)
    if ini <= 0:
        return None
    return round((rec - ini) / ini * 100, 1)


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
    stalled = _stalled_lifts(db, user_id, since)
    stalled_ids = {s["exercise_id"] for s in stalled}
    return TrainingMetrics(
        sessions=n,
        sessions_per_week=round(n / weeks, 2),
        window_days=window_days,
        stalled_lifts=stalled,
        progression_lifts=_progression_lifts(db, user_id, since, stalled_ids),
        volume_trend_pct=_volume_trend(db, user_id, since),
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

    # Marco de recomeço (troca de objetivo): se estiver DENTRO da janela, recorta
    # a leitura pra não misturar a fase antiga. Não apaga nada — só move o início
    # da leitura do coach (os gráficos usam outra rota e seguem mostrando tudo).
    baseline_from = db.execute(
        select(CoachingBaseline.effective_from)
        .where(CoachingBaseline.user_id == user_id)
        .order_by(CoachingBaseline.created_at.desc(), CoachingBaseline.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    # SQLite (dev) devolve datetime SEM tzinfo; `since` é aware. Normaliza pra UTC
    # antes de comparar, senão TypeError (aware vs naive). Postgres já traz aware.
    if baseline_from is not None and baseline_from.tzinfo is None:
        baseline_from = baseline_from.replace(tzinfo=timezone.utc)
    baseline_at: datetime | None = None
    if baseline_from is not None and baseline_from > since:
        since = baseline_from
        baseline_at = baseline_from
        window_days = max(1, (now - since).days)  # janela efetiva, pra ratios justos

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
        baseline_at=baseline_at,
    )
