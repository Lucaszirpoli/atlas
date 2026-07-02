from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.privacy_settings import UserPrivacySettings
from app.models.user import User
from app.schemas.privacy import PrivacySettingsRead, PrivacySettingsUpdate
from app.services.feed_service import get_or_create_privacy

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.get("", response_model=PrivacySettingsRead)
def get_privacy(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserPrivacySettings:
    settings = get_or_create_privacy(db, current_user.id)
    db.commit()
    return settings


@router.patch("", response_model=PrivacySettingsRead)
def update_privacy(
    payload: PrivacySettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPrivacySettings:
    settings = get_or_create_privacy(db, current_user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return settings
