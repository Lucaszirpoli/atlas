from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.coaching.engine import analyze
from app.coaching.metrics import compute_metrics
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import Plan, User
from app.schemas.coaching import CoachingAnalysis

router = APIRouter(prefix="/coaching", tags=["coaching"])


@router.get("/analysis", response_model=CoachingAnalysis)
def coaching_analysis(
    window_days: int = 28,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Análise semanal do Coaching: métricas -> detecção -> ajustes propostos,
    100% determinística (sem token). Exclusiva do Pro — o acompanhamento é o
    valor do plano na reformulação."""
    if current_user.plan != Plan.PRO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="O Coaching é exclusivo do plano Pro.",
        )
    window_days = max(14, min(window_days, 90))
    metrics = compute_metrics(db, current_user.id, window_days=window_days)
    return analyze(metrics).to_dict()
