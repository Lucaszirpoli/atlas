from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_pro_plan
from app.models.user import User
from app.schemas.workout_insights import WorkoutInsightsResponse
from app.services import workout_insights_service

router = APIRouter(prefix="/workout-insights", tags=["workout-insights"])


@router.get("", response_model=WorkoutInsightsResponse)
def get_workout_insights(
    current_user: User = Depends(require_pro_plan), db: Session = Depends(get_db)
) -> dict:
    return {
        "plateaus": workout_insights_service.detect_plateaus(db, current_user.id),
        "deload": workout_insights_service.detect_deload_suggestion(db, current_user.id),
    }
