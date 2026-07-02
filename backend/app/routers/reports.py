from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.content_report import ContentReport
from app.models.user import User
from app.schemas.report import ContentReportCreate

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ContentReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    report = ContentReport(
        reporter_id=current_user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason,
    )
    db.add(report)
    db.commit()
    return {"received": True}
