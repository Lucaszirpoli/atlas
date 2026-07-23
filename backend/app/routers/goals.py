from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.coaching import overlays as coach_overlays
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.calorie_goal import CalorieGoal
from app.models.coaching_baseline import CoachingBaseline
from app.models.user import User
from app.schemas.goal import CalorieGoalAutoSuggestion, CalorieGoalManualCreate, CalorieGoalRead
from app.services import goal_service

router = APIRouter(prefix="/goals/calorie", tags=["goals"])


def _require_profile(current_user: User) -> None:
    if current_user.profile is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onboarding precisa ser concluído antes de definir metas",
        )


@router.get("", response_model=CalorieGoalRead | None)
def get_current_goal(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CalorieGoal | None:
    return goal_service.get_current_goal(db, current_user.id)


@router.get("/suggestion", response_model=CalorieGoalAutoSuggestion)
def get_auto_suggestion(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    _require_profile(current_user)
    try:
        return goal_service.compute_suggestion(db, current_user.id, current_user.profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/auto", response_model=CalorieGoalRead)
def apply_auto_goal(
    as_first_objective: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalorieGoal:
    """Aplica a meta automática. `as_first_objective=true` = "considerar como
    primeiro objetivo": o coach ESQUECE a fase anterior e vai direto pra meta
    nova (sem transição gradual) — e recomeça a análise a partir de agora (marco
    novo), pra não misturar cutting com bulking. Sem a flag, salto grande de kcal
    vira transição gradual."""
    _require_profile(current_user)
    try:
        suggestion = goal_service.compute_suggestion(db, current_user.id, current_user.profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    goal = goal_service.apply_auto_goal(db, current_user.id, suggestion, immediate=as_first_objective)
    if as_first_objective:
        # Recomeça a leitura do coach a partir de agora — esquece a fase anterior.
        # Não apaga histórico (regra 4): só move o ponto de partida da análise.
        db.add(CoachingBaseline(user_id=current_user.id, effective_from=datetime.now(timezone.utc), reason="first_objective"))
        # E limpa os overlays de treino da fase anterior (subir carga, trocar
        # exercício, deload, técnica): eram do objetivo antigo. Sem isto, o treino
        # segue mostrando avisos que a análise nova nem enxerga — e às vezes
        # contraditórios (mandar subir a carga E trocar o mesmo exercício).
        coach_overlays.clear_training_overlays(db, current_user.id)
        db.commit()
    return goal


@router.post("/manual", response_model=CalorieGoalRead)
def apply_manual_goal(
    payload: CalorieGoalManualCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalorieGoal:
    return goal_service.apply_manual_goal(db, current_user.id, payload)
