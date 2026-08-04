"""Camada 1 — MÉTRICAS. Lê o histórico append-only (peso, refeições, sessões,
sono) e destila números objetivos. Sem julgamento aqui: só medir. As camadas de
detecção/diagnóstico é que interpretam.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from statistics import median as _median

from app.coaching.robust_stats import robust_average
from app.core.usertime import local_date, profile_tz, today_local
from app.models.calorie_goal import CalorieGoal
from app.models.coaching_baseline import CoachingBaseline
from app.models.exercise import Exercise, MuscleGroup
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
    # Médias ROBUSTAS (mediana / winsorizada) sobre os dias ENCERRADOS e
    # VÁLIDOS — nunca média simples, nunca o dia de hoje, nunca um dia
    # registrado pela metade. Ver coaching/robust_stats.py e services/day_quality.py.
    avg_kcal_logged: float | None
    avg_protein_logged: float | None
    avg_carbs_logged: float | None
    avg_fat_logged: float | None
    days_logged: int  # dias válidos que entraram na conta
    window_days: int
    # Rastro da estatística, pra UI poder ser honesta sobre confiança.
    avg_method: str = "insuficiente"  # mediana | winsorizada | insuficiente
    avg_confidence: str = "insuficiente"  # insuficiente | baixa | media | alta
    outlier_days: int = 0  # dias cujo peso na média foi limitado (não apagados)
    # Dias encerrados que a pessoa precisa resolver (registro parece incompleto).
    days_needing_attention: list[str] = field(default_factory=list)
    # Dias com algum registro, incluindo os que ficaram fora das médias. Base
    # da métrica de adesão AO REGISTRO, separada da adesão à dieta.
    days_with_any_log: int = 0
    # QUANTO OS DIAS OSCILAM em torno da meta — desvio absoluto médio de cada
    # dia até a meta, em % da meta, por macro.
    #
    # Existe porque a média central MENTE sobre consistência: 48 g de carbo num
    # dia e 283 g no outro tem mediana 165 g contra meta 161 g, e o coach
    # dizia "macros no alvo" — sendo que NENHUM dos dois dias bateu a meta. O
    # desvio se calcula dia a dia ANTES de resumir, então oscilações opostas
    # não se cancelam.
    swing_protein_pct: float | None = None
    swing_carbs_pct: float | None = None
    swing_fat_pct: float | None = None


@dataclass
class TrainingMetrics:
    sessions: int
    sessions_per_week: float
    window_days: int
    # Exercícios principais que pararam de progredir na janela.
    # Cada item: {"exercise_id": int, "name": str, "sessions": int,
    #             "span_days": int, "is_compound": bool, "muscle": str}
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


def _nutrition_metrics(
    db: Session, user_id: int, since: datetime, window_days: int, tz: ZoneInfo
) -> NutritionMetrics:
    """Médias nutricionais da janela. Duas regras da spec §10 mandam aqui:

    - só dia ENCERRADO no fuso da pessoa entra (o dia de hoje está em
      andamento — 300 kcal às 10h não é "a ingestão do dia");
    - só dia VÁLIDO entra (registro pela metade fica de fora até a pessoa
      confirmar ou marcar como incompleto).

    E a média nunca é simples: é mediana ou winsorizada conforme a quantidade
    de dias válidos, pra um churrasco não mandar na leitura do mês.
    """
    from app.services.day_quality import nutrition_days

    dias = nutrition_days(db, user_id, tz, since, include_today=False)
    validos = [d for d in dias if d.valid_for_average]

    kcal = robust_average([d.kcal for d in validos])
    prot = robust_average([d.protein_g for d in validos])
    carb = robust_average([d.carbs_g for d in validos])
    fat = robust_average([d.fat_g for d in validos])

    goal = db.execute(
        select(CalorieGoal)
        .where(CalorieGoal.user_id == user_id)
        .order_by(CalorieGoal.created_at.desc(), CalorieGoal.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    def _round(r, nd: int = 0) -> float | None:
        return None if r.value is None else round(r.value, nd)

    def _swing(valores: list[float], alvo: float | None) -> float | None:
        """Desvio absoluto MÉDIO dos dias até a meta, em % da meta.

        Dia a dia, e só então resumido — é isso que impede 48 g e 283 g de
        virarem "na meta" por se cancelarem. Precisa de pelo menos 3 dias:
        com 1 ou 2, oscilação é ruído, não hábito.
        """
        if not alvo or len(valores) < 3:
            return None
        return round(sum(abs(v - alvo) for v in valores) / len(valores) / alvo * 100, 1)

    return NutritionMetrics(
        goal_kcal=goal.kcal if goal else None,
        goal_protein_g=goal.protein_g if goal else None,
        goal_carbs_g=goal.carbs_g if goal else None,
        goal_fat_g=goal.fat_g if goal else None,
        avg_kcal_logged=_round(kcal),
        avg_protein_logged=_round(prot, 1),
        avg_carbs_logged=_round(carb, 1),
        avg_fat_logged=_round(fat, 1),
        days_logged=len(validos),
        window_days=window_days,
        avg_method=kcal.method,
        avg_confidence=kcal.confidence,
        outlier_days=kcal.outliers,
        days_needing_attention=[d.day.isoformat() for d in dias if d.needs_attention],
        days_with_any_log=len(dias),
        swing_protein_pct=_swing([d.protein_g for d in validos], goal.protein_g if goal else None),
        swing_carbs_pct=_swing([d.carbs_g for d in validos], goal.carbs_g if goal else None),
        swing_fat_pct=_swing([d.fat_g for d in validos], goal.fat_g if goal else None),
    )


def _e1rm(weight_kg: float, reps: int) -> float:
    """1RM estimado (Epley) — capta progresso por carga OU por reps, então uma
    série de 80×8 e outra de 80×10 não parecem 'iguais'."""
    return weight_kg * (1 + reps / 30.0)


def _stalled_lifts(db: Session, user_id: int, since: datetime, tz: ZoneInfo) -> list[dict]:
    """Exercícios principais que não progrediram: pra cada exercício treinado em
    ≥3 sessões num intervalo ≥14 dias, compara o melhor e1RM da metade recente
    com o da metade inicial. Sem ganho (dentro de 1%) = travado. Prioriza
    compostos e os mais treinados; devolve no máximo 2 (não assusta a pessoa)."""
    rows = db.execute(
        select(
            WorkoutSetLog.exercise_id,
            Exercise.name,
            Exercise.is_compound,
            Exercise.primary_muscle_group,
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
            # Mini-set de técnica avançada (myo-reps, cluster) não é série de
            # trabalho: um bloco de 2 reps não diz nada sobre progressão de
            # carga e só faria o e1RM do dia parecer pior do que foi.
            _sem_bloco(),
        )
    ).all()

    # exercise_id -> {name, is_compound, muscle, per_session: {day -> best_e1rm}}
    by_ex: dict[int, dict] = {}
    for ex_id, name, is_comp, muscle, started_at, w, reps in rows:
        d = by_ex.setdefault(ex_id, {
            "name": name, "is_compound": bool(is_comp),
            "muscle": muscle.value if hasattr(muscle, "value") else str(muscle),
            "sessions": {},
        })
        day = local_date(started_at, tz).isoformat()
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
                 "span_days": span, "is_compound": d["is_compound"], "muscle": d["muscle"]}
            )

    # compostos primeiro, depois os mais treinados
    stalled.sort(key=lambda s: (not s["is_compound"], -s["sessions"]))
    return [
        {"exercise_id": s["exercise_id"], "name": s["name"], "sessions": s["sessions"],
         "span_days": s["span_days"], "is_compound": s["is_compound"], "muscle": s["muscle"]}
        for s in stalled[:2]
    ]


# set_types que NÃO são série de trabalho (não valem pro sinal de progressão).
_NON_WORKING_SETS = {"warmup", "feeder"}


def _sem_bloco():
    """Filtro: ignora os MINI-SETS das técnicas avançadas (block_index >= 1).
    A ativação/série principal (block_index 0 ou NULL) continua contando —
    é ela que carrega o peso de trabalho de verdade."""
    from sqlalchemy import or_

    return or_(WorkoutSetLog.block_index.is_(None), WorkoutSetLog.block_index == 0)


def _progression_lifts(
    db: Session, user_id: int, since: datetime, stalled_ids: set[int], tz: ZoneInfo,
    profile: UserProfile | None = None,
) -> list[dict]:
    """Exercícios prontos pra subir a carga: no treino mais recente a pessoa
    bateu o TOPO DA FAIXA PRESCRITA PRA AQUELE EXERCÍCIO na série mais pesada,
    com folga (RIR observado ≥ RIR-alvo daquele exercício, ou não informado). É
    o oposto do platô — por isso exclui quem já está travado. Sinal de coach de
    verdade: 'você tá voando nesse peso, sobe'.

    Cap. XVI Parte D do manual: "compare o RIR-alvo com o RIR observado" antes
    de decidir progressão — nunca um número fixo pra qualquer exercício. Até
    2026-07-31 este sinal usava um teto de 12 reps (18 pra peso corporal) igual
    pra TODOS os exercícios. Deixou de fazer sentido quando a faixa de reps
    passou a variar por exercício (Cap. XI): um agachamento livre prescrito em
    5-9 quase nunca bateria 12 reps (o sinal nunca disparava), e uma elevação
    lateral prescrita em 10-15 disparava aos 12 — antes do topo real da faixa
    dela. Agora o teto e o RIR-alvo vêm da MESMA função que prescreveu o
    exercício (`prescription`), então progressão nunca diverge do que o treino
    realmente pede.

    Devolve no máximo 3, compostos primeiro (subir num composto rende mais)."""
    from app.ai import exercise_taxonomy
    from app.coaching import prescription
    from app.models.exercise import Equipment

    experience = profile.experience_level.value if profile and profile.experience_level else None
    rir_accuracy = getattr(profile, "rir_accuracy", None)
    failure_comfort = getattr(profile, "failure_comfort", None)
    load_preference = getattr(profile, "load_preference", None)

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
            _sem_bloco(),
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
        day = local_date(started_at, tz).isoformat()
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

        # O teto de reps e o RIR-alvo vêm da MESMA prescrição que o motor usou
        # pra montar o treino desse exercício — nunca um número fixo. Exercício
        # que já saiu da taxonomia (renomeado, removido da biblioteca) cai no
        # palpite conservador de `taxon_for`, que ainda assim é MELHOR que um
        # teto igual pra tudo: nunca dispara cedo demais.
        try:
            musculo_enum = MuscleGroup(d["muscle"])
        except ValueError:
            musculo_enum = None
        taxon = exercise_taxonomy.taxon_for(d["name"], musculo_enum, d["is_compound"])
        _, teto = prescription.rep_band(taxon, load_preference=load_preference)
        rir_alvo = prescription.target_rir(
            taxon, experience=experience, rir_accuracy=rir_accuracy,
            failure_comfort=failure_comfort, is_last_set=True,
        )
        folga = rir is None or rir >= rir_alvo
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


def _training_metrics(
    db: Session, user_id: int, since: datetime, window_days: int, tz: ZoneInfo,
    profile: UserProfile | None = None,
) -> TrainingMetrics:
    # Só sessões CONCLUÍDAS contam como treino feito. Diferente da nutrição, um
    # treino concluído JÁ é um evento fechado — não depende da virada do dia
    # pra estar completo. Por isso a regra do "dia em andamento" (§10.1) não se
    # aplica aqui: quem treinou hoje de manhã vê o treino contando hoje mesmo.
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
    stalled = _stalled_lifts(db, user_id, since, tz)
    stalled_ids = {s["exercise_id"] for s in stalled}
    return TrainingMetrics(
        sessions=n,
        sessions_per_week=round(n / weeks, 2),
        window_days=window_days,
        stalled_lifts=stalled,
        progression_lifts=_progression_lifts(db, user_id, since, stalled_ids, tz, profile),
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
    # Sono usa MEDIANA (§10.4): uma virada de noite ou um domingo de 12h
    # deslocam a média e sugeriam um padrão de sono que a pessoa não tem.
    avg_h = None if not hours else round(float(_median(hours)), 1)
    avg_q = round(float(_median([lg.quality for lg in logs])), 1)
    return SleepMetrics(avg_hours=avg_h, avg_quality=avg_q, nights=len(logs))


def compute_metrics(
    db: Session,
    user_id: int,
    window_days: int = 28,
    *,
    now: datetime | None = None,
    since_override: datetime | None = None,
) -> Metrics:
    """Destila as métricas da janela (padrão 4 semanas). `now` é injetável só
    pra teste. `since_override` fixa o início da janela (ex.: o check-in usa o
    começo da SEMANA-calendário, não uma janela móvel de 7 dias) — quando dado,
    pula o clamp de marco (a semana é a semana)."""
    now = now or datetime.now(timezone.utc)
    if since_override is not None:
        since = since_override
        window_days = max(1, (now - since).days)
        return _assemble_metrics(db, user_id, since, window_days, now, baseline_at=None)

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

    return _assemble_metrics(db, user_id, since, window_days, now, baseline_at=baseline_at)


def _assemble_metrics(
    db: Session,
    user_id: int,
    since: datetime,
    window_days: int,
    now: datetime,
    *,
    baseline_at: datetime | None,
) -> Metrics:
    profile = db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    ).scalar_one_or_none()
    goal = profile.goal.value if profile else None
    # Todo agrupamento por DIA daqui pra baixo usa o calendário da pessoa, não
    # o calendário UTC do servidor (ver core/usertime.py).
    tz = profile_tz(profile)

    weight, latest_any = _weight_metrics(db, user_id, since)
    return Metrics(
        window_days=window_days,
        goal=goal,
        weight_kg=weight.latest_kg or latest_any,
        weight=weight,
        nutrition=_nutrition_metrics(db, user_id, since, window_days, tz),
        training=_training_metrics(db, user_id, since, window_days, tz, profile),
        sleep=_sleep_metrics(db, user_id, since),
        baseline_at=baseline_at,
    )
