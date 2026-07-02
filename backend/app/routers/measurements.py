from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.body_measurement import BodyMeasurement, ProgressPhoto
from app.models.user import User
from app.schemas.measurement import (
    BodyMeasurementCreate,
    BodyMeasurementRead,
    ProgressPhotoCreate,
    ProgressPhotoRead,
)

router = APIRouter(tags=["measurements"])


@router.get("/measurements", response_model=list[BodyMeasurementRead])
def list_measurements(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[BodyMeasurement]:
    stmt = (
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == current_user.id)
        .order_by(BodyMeasurement.recorded_at.desc())
    )
    return list(db.execute(stmt).scalars())


@router.post("/measurements", response_model=BodyMeasurementRead, status_code=status.HTTP_201_CREATED)
def create_measurement(
    payload: BodyMeasurementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BodyMeasurement:
    measurement = BodyMeasurement(
        user_id=current_user.id,
        type=payload.type,
        value_cm=payload.value_cm,
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
    )
    db.add(measurement)
    db.commit()
    db.refresh(measurement)
    return measurement


@router.get("/progress-photos", response_model=list[ProgressPhotoRead])
def list_progress_photos(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ProgressPhoto]:
    stmt = (
        select(ProgressPhoto)
        .where(ProgressPhoto.user_id == current_user.id)
        .order_by(ProgressPhoto.recorded_at.desc())
    )
    return list(db.execute(stmt).scalars())


@router.post("/progress-photos", response_model=ProgressPhotoRead, status_code=status.HTTP_201_CREATED)
def create_progress_photo(
    payload: ProgressPhotoCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProgressPhoto:
    photo = ProgressPhoto(
        user_id=current_user.id,
        photo_url=payload.photo_url,
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo
