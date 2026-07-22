from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.coaching import chat as coach_chat
from app.coaching.engine import analyze, suggest_stall_technique
from app.coaching.metrics import compute_metrics
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.calorie_goal import CalorieGoal, GoalMode
from app.models.coaching_adjustment import CoachingAdjustment
from app.models.coaching_baseline import CoachingBaseline
from app.models.coaching_technique_cue import CoachingTechniqueCue
from app.models.user import Plan, User
from app.schemas.coaching import (
    ApplyDietRequest,
    ApplyDietResult,
    ApplyTechniqueRequest,
    ApplyTechniqueResult,
    CoachChatRequest,
    CoachChatResponse,
    CoachingAdjustmentRead,
    CoachingAnalysis,
    RemoveCueResult,
    ResetBaselineResult,
    RevertResult,
    TechniqueCueRead,
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
