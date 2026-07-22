from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.coaching import chat as coach_chat
from app.coaching.engine import analyze, progression_step, suggest_stall_technique, weekly_checkin
from app.coaching.metrics import compute_metrics
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.calorie_goal import CalorieGoal, GoalMode
from app.models.coaching_action import CoachingAction
from app.models.coaching_adjustment import CoachingAdjustment
from app.models.coaching_baseline import CoachingBaseline
from app.models.coaching_technique_cue import CoachingTechniqueCue
from app.models.exercise import Exercise, quality_order
from app.models.user import Plan, User
from app.schemas.coaching import (
    ApplyActionRequest,
    ApplyActionResult,
    ApplyDietRequest,
    ApplyDietResult,
    ApplyTechniqueRequest,
    ApplyTechniqueResult,
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


@router.get("/analysis", response_model=CoachingAnalysis)
def coaching_analysis(
    window_days: int = 28,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Análise semanal do Coaching: métricas -> detecção -> ajustes propostos,
    100% determinística (sem token). Exclusiva do Pro — o acompanhamento é o
    valor do plano na reformulação."""
    _require_pro(current_user)
    window_days = max(7, min(window_days, 90))  # 7 = "Semanal"
    metrics = compute_metrics(db, current_user.id, window_days=window_days)
    return analyze(metrics).to_dict()


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

    tech_key, tech_label, cue_text = suggest_stall_technique(lift["is_compound"])

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
        v = m.training.volume_trend_pct
        if v is None or v > -8:
            raise HTTPException(status_code=409, detail="Sua carga não está mais caindo — o deload não é "
                                "necessário agora. Veja as sugestões atuais.")
        existing = _ja_ativa("deload", None)
        if existing:
            return ApplyActionResult(applied=True, kind="deload", title=existing.title,
                                     message="Você já está numa semana de deload.")
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
    for c in db.execute(
        select(CoachingTechniqueCue).where(
            CoachingTechniqueCue.user_id == current_user.id,
            CoachingTechniqueCue.reverted_at.is_(None),
        )
    ).scalars():
        out.append(WorkoutOverlay(source="technique", id=c.id, kind="technique",
                                  exercise_id=c.exercise_id, exercise_name=c.exercise_name,
                                  title=c.technique_label, detail=c.cue_text, payload={}))
    now = datetime.now(timezone.utc)
    for a in db.execute(
        select(CoachingAction).where(
            CoachingAction.user_id == current_user.id,
            CoachingAction.reverted_at.is_(None),
        )
    ).scalars():
        # deload expira sozinho em 7 dias (some do treino sem precisar desfazer).
        if a.kind == "deload":
            criado = _aware(a.created_at)
            if criado is not None and (now - criado).days >= 7:
                continue
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
    """Check-in semanal proativo — o resumo de segunda-feira do coach. Janela de
    7 dias, determinístico. Exclusivo do Pro."""
    _require_pro(current_user)
    m = compute_metrics(db, current_user.id, window_days=7)
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
    texto, used_ai = coach_chat.answer(analysis, payload.question, history)
    return CoachChatResponse(answer=texto, used_ai=used_ai)


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
