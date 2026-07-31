from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import exercise_taxonomy
from app.coaching import cycle_state, prescription, training_brain
from app.models.coaching_action import CoachingAction
from app.models.exercise import Exercise
from app.models.routine import Routine
from app.models.user import User
from app.models.workout_session import WorkoutSession, WorkoutSetLog


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite (dev) devolve datetime naive; Postgres aware. Normaliza pra UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _inherited_source(db: Session, user_id: int, exercise_id: int) -> int | None:
    """Exercício de onde este herda histórico, quando a pessoa trocou de
    exercício e escolheu MANTER os registros (spec §8.1). Segue a cadeia (A->B->C)
    com teto, pra uma sequência de trocas não virar laço nem consulta infinita."""
    from app.models.exercise_history_link import ExerciseHistoryLink

    atual = exercise_id
    vistos = {atual}
    for _ in range(5):
        origem = db.execute(
            select(ExerciseHistoryLink.inherits_from_exercise_id).where(
                ExerciseHistoryLink.user_id == user_id,
                ExerciseHistoryLink.exercise_id == atual,
            )
        ).scalar_one_or_none()
        if origem is None or origem in vistos:
            break
        vistos.add(origem)
        atual = origem
    return None if atual == exercise_id else atual


def _last_performance_raw(db: Session, user_id: int, exercise_id: int) -> dict | None:
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
                # Mini-set de técnica avançada não serve de referência de carga
                # pra próxima vez — um bloco de 2 reps não é a série de trabalho.
                (WorkoutSetLog.block_index.is_(None)) | (WorkoutSetLog.block_index == 0),
            )
            .order_by(WorkoutSetLog.set_number)
        ).scalars()
    )
    if not sets:
        return None
    return {
        "exercise_id": exercise_id,
        "last_performed_at": session.started_at,
        "sets": [
            {"set_number": s.set_number, "weight_kg": s.weight_kg, "reps": s.reps} for s in sets
        ],
    }


def _active_progression(db: Session, user_id: int, exercise_id: int) -> CoachingAction | None:
    return db.execute(
        select(CoachingAction).where(
            CoachingAction.user_id == user_id,
            CoachingAction.kind == "progression",
            CoachingAction.exercise_id == exercise_id,
            CoachingAction.reverted_at.is_(None),
        )
    ).scalar_one_or_none()


def _com_progressao_aplicada(db: Session, user_id: int, exercise_id: int, base: dict | None) -> dict | None:
    """"Aplicar mudança" precisa valer de verdade na próxima vez — não só
    lembrar (ajuste pós-v36, item 9). Como a rotina-molde não guarda peso (regra
    3: quem tem os números reais é a sessão), o jeito é a carga sugerida virar o
    PRÉ-PREENCHIDO enquanto a ação estiver ativa. Assim que a pessoa registra de
    verdade um treino nesse exercício DEPOIS da sugestão, o log real passa a
    valer sozinho e a ação se consome (reverted_at), sem precisar de botão."""
    acao = _active_progression(db, user_id, exercise_id)
    if acao is None:
        return base

    cumprida = (
        base is not None
        and base.get("last_performed_at") is not None
        and _aware(base["last_performed_at"]) is not None
        and _aware(acao.created_at) is not None
        and _aware(base["last_performed_at"]) >= _aware(acao.created_at)
    )
    if cumprida:
        acao.reverted_at = datetime.now(timezone.utc)
        db.commit()
        return base

    novo_peso = (acao.payload or {}).get("new_weight")
    if novo_peso is None:
        return base

    sets = base["sets"] if base and base.get("sets") else [{"set_number": 1, "reps": acao.payload.get("top_reps")}]
    return {
        **(base or {"exercise_id": exercise_id, "last_performed_at": None}),
        "exercise_id": exercise_id,
        "sets": [{**s, "weight_kg": novo_peso} for s in sets],
        "suggested_by_coach": True,
    }


def get_last_performance(db: Session, user_id: int, exercise_id: int) -> dict | None:
    """Última vez que o usuário executou esse exercício, em qualquer rotina —
    usado para pré-preencher peso/reps na tela de execução.

    Sem registro próprio, cai no exercício de ORIGEM quando houve uma troca com
    "manter registros" — é isso que faz o peso continuar de onde parou depois
    de trocar de exercício, com a origem identificada."""
    proprio = _last_performance_raw(db, user_id, exercise_id)
    if proprio is not None:
        return _com_progressao_aplicada(db, user_id, exercise_id, proprio)

    origem_id = _inherited_source(db, user_id, exercise_id)
    if origem_id is None:
        return _com_progressao_aplicada(db, user_id, exercise_id, None)
    herdado = _last_performance_raw(db, user_id, origem_id)
    if herdado is None:
        return _com_progressao_aplicada(db, user_id, exercise_id, None)
    origem = db.get(Exercise, origem_id)
    return _com_progressao_aplicada(
        db,
        user_id,
        exercise_id,
        {
            **herdado,
            "exercise_id": exercise_id,
            # A UI mostra de onde veio — "carga herdada" sem dizer de quê confunde.
            "inherited_from_name": origem.name if origem else None,
        },
    )


def build_prefill(db: Session, user: User, routine: Routine) -> list[dict]:
    period = cycle_state.current_period(db, user.id)
    rir_do_ciclo = training_brain.suggested_work_rir(period)
    profile = user.profile
    prefill = []
    # Aquecimento entra APENAS quando a sessão começa a trabalhar um grupo
    # ainda não preparado (§6.3). Percorre os exercícios na ORDEM do treino e
    # vai marcando o que já ficou pronto: depois do supino, o tríceps não pede
    # aquecimento geral de novo. Feeder é outra coisa e continua existindo.
    ja_preparados: set = set()
    for routine_exercise in routine.exercises:
        performance = get_last_performance(db, user.id, routine_exercise.exercise_id)
        item = performance or {
            "exercise_id": routine_exercise.exercise_id, "last_performed_at": None, "sets": [],
        }
        item = dict(item)
        # Aquecimento/feeder se baseiam na carga MAIS PESADA das séries de
        # trabalho/falha da última vez (o "mais pesado entre os dois"). Sem
        # histórico o peso vem None (warmup_feeder_ramp_for já trata isso).
        base_weight = max((s["weight_kg"] for s in item["sets"]), default=None)

        exercise = routine_exercise.exercise or db.get(Exercise, routine_exercise.exercise_id)
        muscle = exercise.primary_muscle_group if exercise else None

        # RIR-ALVO por EXERCÍCIO, não um número só pro treino inteiro (Cap. XII).
        # Antes toda série de todo exercício recebia o mesmo RIR do período, o
        # que o manual rejeita: "o RIR não é uma propriedade fixa da categoria do
        # exercício" — ele depende da estabilidade, do risco, de quem encerra a
        # série e da capacidade da pessoa de estimar esforço. Chegar perto da
        # falha num agachamento livre e numa cadeira extensora custa coisas
        # diferentes, e agora a prescrição diz isso.
        #
        # O RIR do ciclo continua mandando quando é ele o mais conservador: na
        # fase de intensificação o motor aperta, mas nunca afrouxa o piso de
        # segurança de um exercício arriscado.
        item["suggested_rir"] = max(
            rir_do_ciclo - 1,
            prescription.target_rir(
                exercise_taxonomy.taxon_for(
                    exercise.name if exercise else "",
                    muscle,
                    bool(exercise.is_compound) if exercise else False,
                ),
                experience=(
                    profile.experience_level.value
                    if profile is not None and profile.experience_level else None
                ),
                rir_accuracy=getattr(profile, "rir_accuracy", None),
                failure_comfort=getattr(profile, "failure_comfort", None),
            ),
        )
        aquecer = muscle is None or training_brain.needs_warmup(muscle, ja_preparados)
        item["warmup_feeder"] = training_brain.warmup_feeder_ramp_for(
            base_weight,
            include_warmup=aquecer,
            include_feeder=training_brain.needs_feeder(
                bool(exercise.is_compound) if exercise else True, warmed=not aquecer
            ),
        )
        if muscle is not None:
            ja_preparados.update(training_brain.prepared_by(muscle))
        prefill.append(item)
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
