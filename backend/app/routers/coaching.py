from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from datetime import datetime, timedelta, timezone

from app.coaching import chat as coach_chat
from app.coaching import training_brain
from app.coaching import workout_builder
from app.coaching.engine import analyze, progression_step, weekly_checkin
from app.coaching.metrics import compute_metrics
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.calorie_goal import CalorieGoal, GoalMode
from app.models.coaching_action import CoachingAction
from app.models.coaching_adjustment import CoachingAdjustment
from app.models.coaching_baseline import CoachingBaseline
from app.models.coaching_technique_cue import CoachingTechniqueCue
from app.models.exercise import Exercise, quality_order
from app.models.routine import Routine
from app.models.user import Plan, User
from app.models.user_profile import GoalPace
from app.services import goal_service
from app.schemas.coaching import (
    ApplyActionRequest,
    ApplyActionResult,
    ApplyDietRequest,
    ApplyDietResult,
    ApplyTechniqueRequest,
    ApplyTechniqueResult,
    BuildWorkoutResult,
    CoachChatRequest,
    CoachChatResponse,
    CoachingAdjustmentRead,
    CoachingAnalysis,
    CoachingChange,
    CoachingCheckin,
    RemoveActionResult,
    RemoveCueResult,
    ResetBaselineResult,
    RevertResult,
    SetGoalConfigResult,
    SetPaceRequest,
    SetTargetWeightRequest,
    SetTrainingPrefsRequest,
    TechniqueCueRead,
    WorkoutOverlay,
)

router = APIRouter(prefix="/coaching", tags=["coaching"])


def _require_pro(user: User) -> None:
    if user.plan != Plan.PRO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="O Coaching é exclusivo do plano Pro.",
        )


def _janela_do_objetivo(db: Session, user_id: int, now: datetime) -> int:
    """Janela da análise = DESDE que a pessoa começou o objetivo atual (o marco).
    Sem marco, usa 56 dias (fase recente). Cap de 180 dias pra não pesar."""
    baseline = _aware(db.execute(
        select(CoachingBaseline.effective_from)
        .where(CoachingBaseline.user_id == user_id)
        .order_by(CoachingBaseline.created_at.desc(), CoachingBaseline.id.desc())
        .limit(1)
    ).scalar_one_or_none())
    if baseline is None:
        return 56
    return max(7, min((now - baseline).days, 180))


def _periodization_of(user: User) -> str:
    profile = getattr(user, "profile", None)
    return training_brain.valid_periodization(getattr(profile, "periodization", None))


def _weeks_accumulating(db: Session, user_id: int, now: datetime) -> float | None:
    """Semanas acumulando desde o começo do ciclo atual — o marco é o ÚLTIMO
    deload aplicado (mesmo já terminado); sem deload, o início do objetivo
    (baseline). É o que diz à ondulatória quando fechar o mesociclo e ao seletor
    de técnica se estamos em acumulação ou intensificação. None = sem referência."""
    # Só deloads que valeram (não revertidos) marcam o começo de um ciclo — um
    # deload desfeito pelo usuário NÃO reseta o mesociclo.
    ref = _aware(db.execute(
        select(CoachingAction.created_at)
        .where(
            CoachingAction.user_id == user_id,
            CoachingAction.kind == "deload",
            CoachingAction.reverted_at.is_(None),
        )
        .order_by(CoachingAction.created_at.desc(), CoachingAction.id.desc())
        .limit(1)
    ).scalar_one_or_none())
    if ref is None:
        ref = _aware(db.execute(
            select(CoachingBaseline.effective_from)
            .where(CoachingBaseline.user_id == user_id)
            .order_by(CoachingBaseline.created_at.desc(), CoachingBaseline.id.desc())
            .limit(1)
        ).scalar_one_or_none())
    if ref is None:
        return None
    return max(0.0, (now - ref).days / 7.0)


def _cycle_context(db: Session, user: User, now: datetime) -> dict:
    """Contexto do ciclo pro coach: periodização escolhida, semanas acumulando,
    se um deload está PLANEJADO (fim de mesociclo na ondulatória) e o período
    (acumulação/intensificação) que escolhe a técnica avançada."""
    periodization = _periodization_of(user)
    weeks = _weeks_accumulating(db, user.id, now)
    return {
        "periodization": periodization,
        "weeks": weeks,
        "planned_deload": training_brain.is_planned_deload(periodization, weeks),
        "period": training_brain.training_period(weeks),
    }


def _training_prefs_block(db: Session, user: User) -> dict | None:
    """Preferências de treino do Coaching + as opções pro card 'Como eu monto seu
    treino'. Inclui o aviso de cardio quando a pessoa optou por treinar sem ele
    e o objetivo se beneficiaria."""
    profile = getattr(user, "profile", None)
    if profile is None:
        return None
    goal = profile.goal.value if profile.goal else None
    wp = training_brain.valid_weak_point(profile.weak_point)
    return {
        "weak_point": wp,
        "weak_point_label": training_brain.WEAK_POINT_LABEL.get(wp) if wp else None,
        "weak_point_options": [{"value": v, "label": l} for v, l in training_brain.WEAK_POINTS],
        "session_length": training_brain.valid_session_length(profile.session_length),
        "session_length_options": [
            {"value": v, "label": label, "range": faixa}
            for v, label, faixa, _ in training_brain.SESSION_LENGTHS
        ],
        "wants_cardio": profile.wants_cardio,
        "periodization": _periodization_of(user),
        "periodization_options": [
            {"value": v, "label": label, "desc": desc}
            for v, label, desc in training_brain.PERIODIZATIONS
        ],
        "cardio_warning": training_brain.cardio_warning(goal, profile.wants_cardio),
    }


def _workout_block(db: Session, user: User) -> dict:
    """Resumo do treino ATIVO da pessoa (todas as rotinas) — o card 'Seu treino'
    mostra o que o coach montou. `built` = já tem treino ativo."""
    rows = list(db.execute(
        select(Routine)
        .options(selectinload(Routine.exercises))
        .where(Routine.user_id == user.id, Routine.is_archived.is_(False))
        .order_by(Routine.id)
    ).scalars())
    routines = [{"id": r.id, "name": r.name, "exercises": len(r.exercises)} for r in rows]
    return {
        "built": len(routines) > 0,
        "count": len(routines),
        "total_exercises": sum(r["exercises"] for r in routines),
        "routines": routines,
    }


@router.get("/analysis", response_model=CoachingAnalysis)
def coaching_analysis(
    window_days: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Análise do Coaching: métricas -> detecção -> ajustes propostos, 100%
    determinística (sem token). Exclusiva do Pro. A janela é o PERÍODO DO OBJETIVO
    atual (desde o marco) — não mais 4/8/12 semanas fixas. Enquanto um deload
    está ativo, a análise não manda forçar (coerência)."""
    _require_pro(current_user)
    now = datetime.now(timezone.utc)
    if window_days is None:
        window_days = _janela_do_objetivo(db, current_user.id, now)
    else:
        window_days = max(7, min(window_days, 180))
    metrics = compute_metrics(db, current_user.id, window_days=window_days, now=now)
    active_deload = _active_deload(db, current_user.id) is not None
    cyc = _cycle_context(db, current_user, now)
    result = analyze(
        metrics,
        active_deload=active_deload,
        periodization=cyc["periodization"],
        planned_deload=cyc["planned_deload"],
        period=cyc["period"],
    ).to_dict()
    _inject_transition(result, db, current_user)
    result["metrics"]["pace"] = _pace_block(db, current_user)
    result["metrics"]["training_prefs"] = _training_prefs_block(db, current_user)
    result["metrics"]["workout"] = _workout_block(db, current_user)
    return result


def _pace_block(db: Session, user: User) -> dict | None:
    """Ritmo atual + as 3 opções (kcal/velocidade/tempo até o alvo) pro card de
    objetivo. options=[] quando o ritmo não se aplica (manutenção/performance)."""
    profile = getattr(user, "profile", None)
    if profile is None:
        return None
    weight = goal_service.get_latest_weight_kg(db, user.id)
    return {
        "current": (profile.goal_pace.value if profile.goal_pace else "normal"),
        "target_weight_kg": profile.target_weight_kg,
        "current_weight_kg": weight,
        "options": goal_service.pace_options(profile, weight),
    }


def _inject_transition(result: dict, db: Session, user: User) -> None:
    """Quando há uma transição de objetivo em andamento, a barra de CALORIAS passa
    a falar da transição (com o passo pra aplicar, respeitando o intervalo) e o
    header ganha o status. Sem transição, nada muda."""
    tr = goal_service.active_transition(db, user.id)
    result["metrics"]["transition"] = None
    if tr is None:
        return
    profile = getattr(user, "profile", None)
    current = goal_service.get_current_goal(db, user.id)
    if profile is None or current is None:
        return
    try:
        sug = goal_service.compute_suggestion(db, user.id, profile)
        target = float(sug["kcal"])
    except ValueError:
        target = float(tr.target_kcal)
    falta = round(target - current.kcal)
    dias = goal_service.days_since_last_goal(db, user.id) or 0
    faltam_dias = max(0, goal_service.TRANSITION_MIN_DAYS - dias)
    subindo = falta > 0

    result["metrics"]["transition"] = {
        "active": True, "target_kcal": round(target), "current_kcal": round(current.kcal),
        "remaining_kcal": falta, "days_until_next": faltam_dias,
    }
    if abs(falta) <= 50:  # praticamente no alvo — o próximo passo conclui
        return

    ins = next((i for i in result["insights"] if i["key"] == "calorias"), None)
    if ins is None:
        return
    sentido = "subindo" if subindo else "descendo"
    ins["title"] = "Transição de objetivo"
    ins["severity"] = "action"
    base = (f"Estou {sentido} sua meta aos poucos pro novo objetivo — de {round(current.kcal)} pra "
            f"~{round(target)} kcal (faltam {abs(falta)}). Mudança gradual protege o resultado e o corpo.")
    if faltam_dias > 0:
        ins["detail"] = base + f" Próximo passo em {faltam_dias} dia(s)."
        ins["finding_key"] = None
        ins["adjustment"] = None
    else:
        ins["detail"] = base
        ins["finding_key"] = "transition_step"
        ins["adjustment"] = {"kind": "transition"}


@router.post("/apply/diet", response_model=ApplyDietResult)
def apply_diet_adjustment(
    payload: ApplyDietRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplyDietResult:
    """Aplica o ajuste calórico proposto por um achado do Coaching. Reroda a
    análise no servidor pra pegar o delta ATUAL (não confia num valor vindo do
    app) e cria uma NOVA versão da meta — CalorieGoal é append-only e a mais
    recente é a que vale, então isso é o versionamento com fonte única.
    O carbo absorve o delta (energia perto do treino); proteína e gordura ficam.
    """
    _require_pro(current_user)

    analysis = analyze(compute_metrics(db, current_user.id))
    finding = next((f for f in analysis.findings if f.key == payload.finding_key), None)
    delta = finding.adjustment.get("kcal_delta") if finding and finding.adjustment else None
    if delta is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esse ajuste não está mais disponível — sua análise mudou. Veja as sugestões atuais.",
        )

    goal = db.execute(
        select(CalorieGoal)
        .where(CalorieGoal.user_id == current_user.id)
        .order_by(CalorieGoal.created_at.desc(), CalorieGoal.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Defina sua meta de calorias antes de aplicar um ajuste.",
        )

    new_kcal = max(1000.0, round(goal.kcal + int(delta)))  # piso de segurança
    actual_delta = int(round(new_kcal - goal.kcal))
    new_carbs = max(0.0, round(goal.carbs_g + actual_delta / 4.0))  # 1 g carbo = 4 kcal

    novo = CalorieGoal(
        user_id=current_user.id,
        mode=GoalMode.MANUAL,  # ajuste do coach vira alvo fixo (não recalculado)
        kcal=new_kcal,
        protein_g=goal.protein_g,
        carbs_g=new_carbs,
        fat_g=goal.fat_g,
        fiber_g=goal.fiber_g,
        sodium_mg=goal.sodium_mg,
        sugar_g=goal.sugar_g,
    )
    db.add(novo)
    # Registro auditável com o snapshot ANTERIOR — é o que o "Desfazer" restaura.
    db.add(
        CoachingAdjustment(
            user_id=current_user.id,
            finding_key=finding.key,
            kind="diet_kcal",
            kcal_delta=actual_delta,
            prev_kcal=goal.kcal,
            prev_protein_g=goal.protein_g,
            prev_carbs_g=goal.carbs_g,
            prev_fat_g=goal.fat_g,
            new_kcal=new_kcal,
        )
    )
    db.commit()

    sentido = "aumentei" if actual_delta > 0 else "reduzi"
    return ApplyDietResult(
        applied=True,
        previous_kcal=goal.kcal,
        new_kcal=new_kcal,
        kcal_delta=actual_delta,
        message=f"Pronto — {sentido} sua meta em {abs(actual_delta)} kcal, agora {round(new_kcal)} kcal/dia. "
        "Reavalie em 2 semanas.",
    )


@router.post("/pace", response_model=SetGoalConfigResult)
def set_pace(
    payload: SetPaceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SetGoalConfigResult:
    """Troca o ritmo do objetivo (devagar/normal/rápido) e recalcula a meta. Se a
    mudança de kcal for grande, entra na transição gradual (não estoura de uma
    vez). Pro."""
    _require_pro(current_user)
    profile = getattr(current_user, "profile", None)
    if profile is None:
        raise HTTPException(status_code=400, detail="Complete seu perfil primeiro.")
    try:
        profile.goal_pace = GoalPace(payload.pace)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ritmo inválido.")
    db.commit()
    try:
        sug = goal_service.compute_suggestion(db, current_user.id, profile)
        goal = goal_service.apply_auto_goal(db, current_user.id, sug)
    except ValueError:
        return SetGoalConfigResult(ok=True, message="Ritmo atualizado. Registre seu peso pra eu ajustar a meta.")
    rot = {"slow": "mais devagar", "normal": "no ritmo recomendado", "fast": "mais rápido"}.get(payload.pace, "")
    return SetGoalConfigResult(ok=True, message=f"Ritmo {rot} — meta agora {round(goal.kcal)} kcal/dia.")


@router.post("/target-weight", response_model=SetGoalConfigResult)
def set_target_weight(
    payload: SetTargetWeightRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SetGoalConfigResult:
    """Define (ou limpa) o peso-alvo — é o que dá a estimativa de tempo por ritmo.
    Não recalcula a meta (o alvo é referência de tempo, não muda o déficit). Pro."""
    _require_pro(current_user)
    profile = getattr(current_user, "profile", None)
    if profile is None:
        raise HTTPException(status_code=400, detail="Complete seu perfil primeiro.")
    profile.target_weight_kg = payload.target_weight_kg
    db.commit()
    if payload.target_weight_kg is None:
        return SetGoalConfigResult(ok=True, message="Peso-alvo removido.")
    return SetGoalConfigResult(ok=True, message=f"Peso-alvo: {payload.target_weight_kg:g} kg. Agora estimo o tempo por ritmo.")


@router.post("/training-prefs", response_model=SetGoalConfigResult)
def set_training_prefs(
    payload: SetTrainingPrefsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SetGoalConfigResult:
    """Define as preferências de treino do Coaching — ponto fraco, tempo por
    sessão, cardio e periodização. Atualização PARCIAL (só os campos enviados) e
    validada aqui: valor inválido não derruba a requisição, cai no seguro. É isto
    que o coach usa pra montar/ajustar treino, escolher técnica e decidir deload."""
    _require_pro(current_user)
    profile = getattr(current_user, "profile", None)
    if profile is None:
        raise HTTPException(status_code=400, detail="Complete seu perfil primeiro.")
    enviados = payload.model_fields_set
    if "weak_point" in enviados:
        profile.weak_point = training_brain.valid_weak_point(payload.weak_point)
    if "session_length" in enviados:
        profile.session_length = training_brain.valid_session_length(payload.session_length)
    if "wants_cardio" in enviados:
        profile.wants_cardio = payload.wants_cardio
    if "periodization" in enviados:
        profile.periodization = training_brain.valid_periodization(payload.periodization)
    db.commit()
    return SetGoalConfigResult(ok=True, message="Preferências de treino atualizadas — o coach já monta e ajusta com elas.")


@router.post("/build-workout", response_model=BuildWorkoutResult)
def build_workout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BuildWorkoutResult:
    """Monta o TREINO COMPLETO da pessoa a partir do 'Como eu monto seu treino':
    escolhe o método que casa com experiência/objetivo/frequência, aplica ponto
    fraco + tempo por sessão, e SALVA como as rotinas ativas (arquiva as antigas —
    não deleta, regra 4). A troca de UM exercício específico continua nas barras;
    aqui é o treino inteiro. Determinístico (sem IA). Pro."""
    _require_pro(current_user)
    try:
        return BuildWorkoutResult(**workout_builder.build_and_save(db, current_user))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/apply/transition", response_model=ApplyDietResult)
def apply_transition_step(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplyDietResult:
    """Dá o próximo passo da transição de objetivo — move a meta um degrau (±250
    kcal) rumo ao alvo, respeitando o intervalo mínimo entre passos. Loga como
    ajuste de dieta (aparece no painel 'O que o coach mudou', com Desfazer)."""
    _require_pro(current_user)
    profile = getattr(current_user, "profile", None)
    if profile is None:
        raise HTTPException(status_code=400, detail="Complete seu perfil primeiro.")
    try:
        r = goal_service.step_transition_goal(db, current_user.id, profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    prev, novo = r["prev_goal"], r["new_goal"]
    delta = int(round(novo.kcal - prev.kcal))
    db.add(CoachingAdjustment(
        user_id=current_user.id, finding_key="transition_step", kind="diet_transition",
        kcal_delta=delta, prev_kcal=prev.kcal, prev_protein_g=prev.protein_g,
        prev_carbs_g=prev.carbs_g, prev_fat_g=prev.fat_g, new_kcal=novo.kcal,
    ))
    db.commit()
    if r["completed"]:
        msg = f"Transição concluída — sua meta chegou em {round(novo.kcal)} kcal, o alvo do novo objetivo. 🎯"
    else:
        msg = (f"Mais um passo: meta agora {round(novo.kcal)} kcal (rumo a ~{round(r['target_kcal'])}). "
               "Segue firme uns dias antes do próximo.")
    return ApplyDietResult(applied=True, previous_kcal=prev.kcal, new_kcal=novo.kcal,
                           kcal_delta=delta, message=msg)


@router.post("/apply/technique", response_model=ApplyTechniqueResult)
def apply_technique(
    payload: ApplyTechniqueRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplyTechniqueResult:
    """Aplica uma técnica de intensidade ao exercício travado — vira uma DICA do
    coach que aparece na prévia do treino (não altera a rotina-molde: regra 3, a
    técnica é conceito de execução). Como no ajuste de dieta, o servidor rederiva
    a técnica do estado ATUAL (não confia num valor vindo do app) e é reversível
    (o app remove a dica). Append-only: aplicar cria uma linha."""
    _require_pro(current_user)

    # finding_key = "stalled_lift:{exercise_id}"
    try:
        exercise_id = int(payload.finding_key.split(":", 1)[1])
    except (IndexError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sugestão inválida.")

    metrics = compute_metrics(db, current_user.id)
    lift = next((s for s in metrics.training.stalled_lifts if s["exercise_id"] == exercise_id), None)
    if lift is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esse exercício não está mais travado — sua análise mudou. Veja as sugestões atuais.",
        )

    # Rederiva a técnica do MESMO jeito que a barra sugeriu: por tipo de exercício
    # + período do ciclo. Não confia num valor vindo do app.
    period = _cycle_context(db, current_user, datetime.now(timezone.utc))["period"]
    tech_key, tech_label, cue_text = training_brain.suggest_technique(lift["is_compound"], period)

    # Idempotente: se já existe dica ativa pra esse exercício, não duplica.
    existing = db.execute(
        select(CoachingTechniqueCue).where(
            CoachingTechniqueCue.user_id == current_user.id,
            CoachingTechniqueCue.exercise_id == exercise_id,
            CoachingTechniqueCue.reverted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return ApplyTechniqueResult(
            applied=True,
            exercise_name=existing.exercise_name,
            technique_label=existing.technique_label,
            message=f"{existing.technique_label} já está aplicado no {existing.exercise_name} — "
            "aparece na prévia do treino.",
        )

    db.add(
        CoachingTechniqueCue(
            user_id=current_user.id,
            finding_key=payload.finding_key,
            exercise_id=exercise_id,
            exercise_name=lift["name"],
            technique=tech_key,
            technique_label=tech_label,
            cue_text=cue_text,
        )
    )
    db.commit()
    return ApplyTechniqueResult(
        applied=True,
        exercise_name=lift["name"],
        technique_label=tech_label,
        message=f"Pronto — {tech_label} entra na prévia do {lift['name']}. Dá pra remover lá quando quiser.",
    )


@router.get("/technique-cues", response_model=list[TechniqueCueRead])
def list_technique_cues(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CoachingTechniqueCue]:
    """Dicas de técnica ATIVAS do usuário (não removidas). A prévia do treino usa
    pra mostrar em cima do exercício correspondente. Livre pra qualquer plano ler
    (não gera nada — só reflete o que o Pro já aplicou)."""
    return list(
        db.execute(
            select(CoachingTechniqueCue)
            .where(
                CoachingTechniqueCue.user_id == current_user.id,
                CoachingTechniqueCue.reverted_at.is_(None),
            )
            .order_by(CoachingTechniqueCue.created_at.desc(), CoachingTechniqueCue.id.desc())
        ).scalars()
    )


@router.post("/technique-cues/{cue_id}/remove", response_model=RemoveCueResult)
def remove_technique_cue(
    cue_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RemoveCueResult:
    """Remove uma dica de técnica (o 'desfazer'): marca reverted_at, não deleta —
    fica no histórico. Some da prévia do treino."""
    cue = db.get(CoachingTechniqueCue, cue_id)
    if cue is None or cue.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dica não encontrada")
    if cue.reverted_at is not None:
        return RemoveCueResult(removed=True, message="Essa dica já tinha sido removida.")
    cue.reverted_at = datetime.now(timezone.utc)
    db.commit()
    return RemoveCueResult(removed=True, message=f"{cue.technique_label} removido do {cue.exercise_name}.")


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite (dev) devolve datetime naive; Postgres aware. Normaliza pra UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


DELOAD_DAYS = 7


def _active_deload(db: Session, user_id: int) -> CoachingAction | None:
    """Deload em andamento (aplicado há < 7 dias e não desfeito). É o que torna o
    coach COERENTE: enquanto vale, ele não manda subir carga nem aplicar técnica."""
    now = datetime.now(timezone.utc)
    for a in db.execute(
        select(CoachingAction).where(
            CoachingAction.user_id == user_id,
            CoachingAction.kind == "deload",
            CoachingAction.reverted_at.is_(None),
        )
    ).scalars():
        criado = _aware(a.created_at)
        if criado is None or (now - criado).days < DELOAD_DAYS:
            return a
    return None


def _semana_atual_inicio(now: datetime) -> datetime:
    """Início da SEMANA-calendário (domingo 00:00), como o app já mostra
    (D S T Q Q S S). Não é janela móvel de 7 dias — é a semana de verdade."""
    dias_desde_domingo = (now.weekday() + 1) % 7  # Mon=0..Sun=6 -> domingo=0
    inicio = now - timedelta(days=dias_desde_domingo)
    return inicio.replace(hour=0, minute=0, second=0, microsecond=0)


def _swap_alternative(db: Session, ex_id: int) -> Exercise | None:
    """Melhor substituto (dos 50 visíveis) pra um exercício travado: mesmo grupo
    muscular, mesmo tipo (composto/isolado), equipamento DIFERENTE de preferência
    — trocar barra por halter/máquina muda o estímulo e costuma furar o platô."""
    orig = db.get(Exercise, ex_id)
    if orig is None:
        return None
    base = select(Exercise).where(
        Exercise.primary_muscle_group == orig.primary_muscle_group,
        Exercise.is_hidden.is_(False),
        Exercise.is_custom.is_(False),
        Exercise.id != ex_id,
    )
    mesmos = list(db.execute(
        base.where(Exercise.is_compound.is_(orig.is_compound)).order_by(*quality_order())
    ).scalars())
    pool = mesmos or list(db.execute(base.order_by(*quality_order())).scalars())
    if not pool:
        return None
    outro_equip = next((e for e in pool if e.equipment != orig.equipment), None)
    return outro_equip or pool[0]


@router.post("/apply/action", response_model=ApplyActionResult)
def apply_action(
    payload: ApplyActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplyActionResult:
    """Aplica uma ação de treino do coach: progressão (subir carga), deload
    (semana leve) ou troca de exercício. Como no resto, o servidor REDERIVA do
    estado atual (não confia no app), é idempotente e reversível. Cria uma
    CoachingAction — overlay no treino, sem mexer na rotina-molde (regra 3)."""
    _require_pro(current_user)
    fk = payload.finding_key
    m = compute_metrics(db, current_user.id)

    def _ja_ativa(kind: str, exercise_id: int | None) -> CoachingAction | None:
        return db.execute(
            select(CoachingAction).where(
                CoachingAction.user_id == current_user.id,
                CoachingAction.kind == kind,
                CoachingAction.exercise_id == exercise_id,
                CoachingAction.reverted_at.is_(None),
            )
        ).scalar_one_or_none()

    if fk.startswith("progression:"):
        try:
            ex_id = int(fk.split(":", 1)[1])
        except ValueError:
            raise HTTPException(status_code=400, detail="Sugestão inválida.")
        # Coerência: não manda subir carga durante um deload.
        if _active_deload(db, current_user.id) is not None:
            raise HTTPException(status_code=409, detail="Você está numa semana de deload — o foco agora é "
                                "recuperar. Subir carga volta quando o deload terminar.")
        p = next((x for x in m.training.progression_lifts if x["exercise_id"] == ex_id), None)
        if p is None:
            raise HTTPException(status_code=409, detail="Esse exercício não está mais pronto pra subir — "
                                "sua análise mudou. Veja as sugestões atuais.")
        existing = _ja_ativa("progression", ex_id)
        if existing:
            return ApplyActionResult(applied=True, kind="progression", title=existing.title,
                                     message=f"{existing.title} já está no seu treino.")
        _, novo, como = progression_step(p["muscle"], p["equipment"], p["top_weight"])
        title = f"Subir carga · {p['name']}"
        db.add(CoachingAction(user_id=current_user.id, kind="progression", finding_key=fk,
                              exercise_id=ex_id, exercise_name=p["name"], title=title, detail=como,
                              payload={"new_weight": novo, "top_weight": p["top_weight"], "top_reps": p["top_reps"]}))
        db.commit()
        alvo = f"pra {novo:g} kg " if novo is not None else ""
        return ApplyActionResult(applied=True, kind="progression", title=title,
                                 message=f"Feito — o coach vai te lembrar de subir {alvo}no {p['name']} "
                                 "na próxima vez. Aparece no treino.")

    if fk == "deload":
        # A periodização manda: linear nunca desloada; ondulatória aceita o deload
        # PLANEJADO (fim de mesociclo) mesmo com a carga ainda subindo; automática
        # exige que a carga esteja caindo (fadiga). Rederiva do estado atual.
        cyc = _cycle_context(db, current_user, datetime.now(timezone.utc))
        if cyc["periodization"] == "linear":
            raise HTTPException(status_code=409, detail="No seu plano linear a gente não usa deload — se a carga "
                                "travou, o caminho é cuidar do sono e da recuperação, não aliviar. Veja as sugestões atuais.")
        v = m.training.volume_trend_pct
        worthy = v is not None and v <= -8
        if not (cyc["planned_deload"] or worthy):
            raise HTTPException(status_code=409, detail="O deload não é necessário agora — sua carga não está caindo "
                                "e você ainda não fechou o mesociclo. Veja as sugestões atuais.")
        existing = _ja_ativa("deload", None)
        if existing:
            return ApplyActionResult(applied=True, kind="deload", title=existing.title,
                                     message="Você já está numa semana de deload.")
        # Coerência: um deload cancela as ações que mandam FORÇAR (subir carga,
        # trocar por estímulo novo) — elas se contradizem com uma semana leve.
        # Voltam a ser oferecidas depois, quando a análise rodar de novo.
        agora = datetime.now(timezone.utc)
        for act in db.execute(
            select(CoachingAction).where(
                CoachingAction.user_id == current_user.id,
                CoachingAction.kind.in_(["progression", "exercise_swap"]),
                CoachingAction.reverted_at.is_(None),
            )
        ).scalars():
            act.reverted_at = agora
        title = "Semana de deload"
        detail = ("Semana leve pra recuperar: reduza a carga em ~40% (ou faça metade das séries valendo), "
                  "mantenha a técnica afiada e pare 2–3 reps antes da falha. Semana que vem você volta mais "
                  "forte — deload não é perder progresso, é o que permite continuar progredindo.")
        db.add(CoachingAction(user_id=current_user.id, kind="deload", finding_key=fk,
                              exercise_id=None, exercise_name=None, title=title, detail=detail, payload={}))
        db.commit()
        return ApplyActionResult(applied=True, kind="deload", title=title,
                                 message="Semana de deload ativada — aparece um lembrete no topo dos seus treinos "
                                 "por 7 dias.")

    if fk.startswith("swap:"):
        try:
            ex_id = int(fk.split(":", 1)[1])
        except ValueError:
            raise HTTPException(status_code=400, detail="Sugestão inválida.")
        lift = next((s for s in m.training.stalled_lifts if s["exercise_id"] == ex_id), None)
        if lift is None:
            raise HTTPException(status_code=409, detail="Esse exercício não está mais travado — "
                                "sua análise mudou. Veja as sugestões atuais.")
        existing = _ja_ativa("exercise_swap", ex_id)
        if existing:
            return ApplyActionResult(applied=True, kind="exercise_swap", title=existing.title,
                                     message=f"{existing.title} já está no seu treino.")
        alt = _swap_alternative(db, ex_id)
        if alt is None:
            raise HTTPException(status_code=409, detail="Não achei uma variação boa pra trocar agora.")
        title = f"Trocar · {lift['name']} → {alt.name}"
        detail = (f"Troque {lift['name']} por {alt.name} por 3–4 semanas. Um estímulo novo no mesmo músculo "
                  "costuma furar o platô — depois você pode voltar mais forte no exercício original.")
        db.add(CoachingAction(user_id=current_user.id, kind="exercise_swap", finding_key=fk,
                              exercise_id=ex_id, exercise_name=lift["name"], title=title, detail=detail,
                              payload={"to_exercise_id": alt.id, "to_name": alt.name}))
        db.commit()
        return ApplyActionResult(applied=True, kind="exercise_swap", title=title,
                                 message=f"Feito — o coach sugere {alt.name} no lugar de {lift['name']}. "
                                 "Aparece no treino.")

    raise HTTPException(status_code=400, detail="Ação desconhecida.")


@router.get("/overlays", response_model=list[WorkoutOverlay])
def workout_overlays(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkoutOverlay]:
    """Overlays ATIVOS do coach pro lado do treino: dicas de técnica + ações
    (progressão/troca por exercício, deload global). A prévia e a execução leem
    isto e mostram em cima do exercício certo (ou no topo, no caso do deload)."""
    out: list[WorkoutOverlay] = []
    deload = _active_deload(db, current_user.id)
    # Coerência: durante o deload, o treino mostra SÓ o banner de deload — nada de
    # técnica de intensidade nem "subir carga", que contradizem a semana leve.
    if deload is not None:
        return [WorkoutOverlay(source="action", id=deload.id, kind="deload",
                               exercise_id=None, exercise_name=None,
                               title=deload.title, detail=deload.detail, payload={})]

    for c in db.execute(
        select(CoachingTechniqueCue).where(
            CoachingTechniqueCue.user_id == current_user.id,
            CoachingTechniqueCue.reverted_at.is_(None),
        )
    ).scalars():
        out.append(WorkoutOverlay(source="technique", id=c.id, kind="technique",
                                  exercise_id=c.exercise_id, exercise_name=c.exercise_name,
                                  title=c.technique_label, detail=c.cue_text, payload={}))
    for a in db.execute(
        select(CoachingAction).where(
            CoachingAction.user_id == current_user.id,
            CoachingAction.kind != "deload",
            CoachingAction.reverted_at.is_(None),
        )
    ).scalars():
        out.append(WorkoutOverlay(source="action", id=a.id, kind=a.kind,
                                  exercise_id=a.exercise_id, exercise_name=a.exercise_name,
                                  title=a.title, detail=a.detail, payload=a.payload or {}))
    return out


@router.get("/changes", response_model=list[CoachingChange])
def coaching_changes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CoachingChange]:
    """Feed unificado 'O que o coach mudou': dieta + técnica + ações, numa lista
    só, mais recente primeiro. O app mostra os ativos e joga o resto no histórico.
    `source`+`ref_id` dizem qual endpoint desfaz cada um."""
    _require_pro(current_user)
    items: list[CoachingChange] = []

    for a in db.execute(
        select(CoachingAdjustment)
        .where(CoachingAdjustment.user_id == current_user.id)
        .order_by(CoachingAdjustment.created_at.desc(), CoachingAdjustment.id.desc())
        .limit(20)
    ).scalars():
        sinal = "+" if a.kcal_delta > 0 else ""
        items.append(CoachingChange(
            source="diet", ref_id=a.id, icon="nutrition",
            title=f"Meta {sinal}{round(a.kcal_delta)} kcal",
            subtitle=f"{round(a.prev_kcal)} → {round(a.new_kcal)} kcal/dia",
            created_at=a.created_at, active=a.reverted_at is None,
        ))

    for c in db.execute(
        select(CoachingTechniqueCue)
        .where(CoachingTechniqueCue.user_id == current_user.id)
        .order_by(CoachingTechniqueCue.created_at.desc(), CoachingTechniqueCue.id.desc())
        .limit(20)
    ).scalars():
        items.append(CoachingChange(
            source="technique", ref_id=c.id, icon="barbell",
            title=f"{c.technique_label} · {c.exercise_name}",
            subtitle="técnica no treino", created_at=c.created_at, active=c.reverted_at is None,
        ))

    _ICON = {"progression": "trending-up", "exercise_swap": "swap-horizontal", "deload": "bed"}
    _SUB = {"progression": "subir carga", "exercise_swap": "troca de exercício", "deload": "semana leve"}
    for a in db.execute(
        select(CoachingAction)
        .where(CoachingAction.user_id == current_user.id)
        .order_by(CoachingAction.created_at.desc(), CoachingAction.id.desc())
        .limit(20)
    ).scalars():
        items.append(CoachingChange(
            source="action", ref_id=a.id, icon=_ICON.get(a.kind, "flash"),
            title=a.title, subtitle=_SUB.get(a.kind, "ação no treino"),
            created_at=a.created_at, active=a.reverted_at is None,
        ))

    items.sort(key=lambda c: c.created_at, reverse=True)
    return items


@router.post("/actions/{action_id}/revert", response_model=RemoveActionResult)
def revert_action(
    action_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RemoveActionResult:
    """Desfaz uma ação de treino (progressão/troca/deload): marca reverted_at,
    não deleta. Some dos overlays do treino."""
    a = db.get(CoachingAction, action_id)
    if a is None or a.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ação não encontrada")
    if a.reverted_at is not None:
        return RemoveActionResult(removed=True, message="Essa ação já tinha sido desfeita.")
    a.reverted_at = datetime.now(timezone.utc)
    db.commit()
    return RemoveActionResult(removed=True, message=f"Desfeito — {a.title} saiu do seu treino.")


@router.get("/checkin", response_model=CoachingCheckin)
def coaching_checkin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Check-in proativo — o balanço da SEMANA-calendário (domingo → agora), não
    uma janela móvel de 7 dias. Determinístico. Exclusivo do Pro."""
    _require_pro(current_user)
    now = datetime.now(timezone.utc)
    m = compute_metrics(db, current_user.id, now=now, since_override=_semana_atual_inicio(now))
    return weekly_checkin(m)


@router.post("/baseline/reset", response_model=ResetBaselineResult)
def reset_baseline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResetBaselineResult:
    """Recomeça a análise do coach a partir de agora (ao trocar de objetivo). A
    partir daqui, a análise só olha os dados NOVOS — não mistura a fase anterior.
    NÃO apaga nada (regra 4): peso, refeições e treinos seguem intactos e os
    gráficos continuam mostrando todo o histórico. Append-only: cada recomeço é
    uma linha nova; a mais recente vale."""
    _require_pro(current_user)
    now = datetime.now(timezone.utc)
    db.add(CoachingBaseline(user_id=current_user.id, effective_from=now, reason="goal_change"))
    db.commit()
    return ResetBaselineResult(
        reset=True,
        effective_from=now,
        message="Análise recomeçada a partir de hoje. Seu histórico e gráficos continuam intactos.",
    )


@router.post("/chat", response_model=CoachChatResponse)
def coach_chat_turn(
    payload: CoachChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CoachChatResponse:
    """Pergunte ao coach. A IA responde ANCORADA na análise determinística (não
    recalcula nada, não muda plano). Exclusiva do Pro; sem chave da Anthropic,
    devolve um resumo determinístico da análise."""
    _require_pro(current_user)
    analysis = analyze(compute_metrics(db, current_user.id))
    history = [{"role": h.role, "content": h.content} for h in payload.history]
    result = coach_chat.answer(db, current_user, analysis, payload.question, history)
    return CoachChatResponse(**result)


@router.get("/adjustments", response_model=list[CoachingAdjustmentRead])
def list_adjustments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CoachingAdjustment]:
    """Histórico recente de ajustes aplicados (com quais já foram desfeitos).
    O app usa pra mostrar 'ajustes que você aplicou' e oferecer Desfazer."""
    _require_pro(current_user)
    return list(
        db.execute(
            select(CoachingAdjustment)
            .where(CoachingAdjustment.user_id == current_user.id)
            .order_by(CoachingAdjustment.created_at.desc(), CoachingAdjustment.id.desc())
            .limit(5)
        ).scalars()
    )


@router.post("/adjustments/{adjustment_id}/revert", response_model=RevertResult)
def revert_adjustment(
    adjustment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RevertResult:
    """Desfaz um ajuste: restaura a meta pro snapshot de ANTES dele, criando uma
    nova versão (append-only). Não desfaz duas vezes."""
    _require_pro(current_user)
    adj = db.get(CoachingAdjustment, adjustment_id)
    if adj is None or adj.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ajuste não encontrado")
    if adj.reverted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Esse ajuste já foi desfeito."
        )

    db.add(
        CalorieGoal(
            user_id=current_user.id,
            mode=GoalMode.MANUAL,
            kcal=adj.prev_kcal,
            protein_g=adj.prev_protein_g,
            carbs_g=adj.prev_carbs_g,
            fat_g=adj.prev_fat_g,
        )
    )
    adj.reverted_at = datetime.now(timezone.utc)
    db.commit()
    return RevertResult(
        reverted=True,
        restored_kcal=adj.prev_kcal,
        message=f"Desfeito — sua meta voltou pra {round(adj.prev_kcal)} kcal/dia.",
    )
