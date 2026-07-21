from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.coaching.engine import analyze
from app.coaching.metrics import compute_metrics
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.calorie_goal import CalorieGoal, GoalMode
from app.models.coaching_adjustment import CoachingAdjustment
from app.models.user import Plan, User
from app.schemas.coaching import (
    ApplyDietRequest,
    ApplyDietResult,
    CoachingAdjustmentRead,
    CoachingAnalysis,
    RevertResult,
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
    window_days = max(14, min(window_days, 90))
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
