from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.calorie_goal import CalorieGoal
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
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CalorieGoal:
    _require_profile(current_user)
    try:
        suggestion = goal_service.compute_suggestion(db, current_user.id, current_user.profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return goal_service.apply_auto_goal(db, current_user.id, suggestion)


@router.post("/manual", response_model=CalorieGoalRead)
def apply_manual_goal(
    payload: CalorieGoalManualCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalorieGoal:
    return goal_service.apply_manual_goal(db, current_user.id, payload)
