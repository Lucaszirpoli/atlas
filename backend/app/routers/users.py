from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.consent import ConsentRecord, ConsentType
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.weight_log import WeightLog
from app.schemas.onboarding import OnboardingRequest, OnboardingResponse
from app.schemas.user import HandleAvailabilityResponse, UserRead
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])

CONSENT_VERSION = "1.0"


@router.get("/handle-availability/{handle}", response_model=HandleAvailabilityResponse)
def check_handle_availability(handle: str, db: Session = Depends(get_db)) -> HandleAvailabilityResponse:
    return HandleAvailabilityResponse(
        handle=handle, available=user_service.handle_is_available(db, handle)
    )


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/onboarding", response_model=OnboardingResponse)
def complete_onboarding(
    payload: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnboardingResponse:
    if current_user.profile is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onboarding já foi concluído para este usuário",
        )

    partner_user_id = None
    if payload.trains_with_partner and payload.partner_handle:
        partner = user_service.get_by_handle(db, payload.partner_handle)
        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parceiro(a) não encontrado(a) pelo handle informado",
            )
        partner_user_id = partner.id

    profile = UserProfile(
        user_id=current_user.id,
        biological_sex=payload.biological_sex,
        age=payload.age,
        height_cm=payload.height_cm,
        activity_level=payload.activity_level,
        goal=payload.goal,
        experience_level=payload.experience_level,
        training_location=payload.training_location,
        training_style_preference=payload.training_style_preference,
        available_days=payload.available_days,
        dietary_restrictions=payload.dietary_restrictions,
        injuries_limitations=payload.injuries_limitations,
        preferred_advanced_technique=payload.preferred_advanced_technique,
        trains_with_partner=payload.trains_with_partner,
        partner_user_id=partner_user_id,
    )
    db.add(profile)

    now = datetime.now(timezone.utc)
    db.add(
        WeightLog(
            user_id=current_user.id,
            weight_kg=payload.current_weight_kg,
            recorded_at=now,
        )
    )
    db.add(
        ConsentRecord(
            user_id=current_user.id,
            consent_type=ConsentType.LGPD_HEALTH_DATA,
            version=CONSENT_VERSION,
            accepted=payload.accepted_lgpd_health_data,
        )
    )
    db.add(
        ConsentRecord(
            user_id=current_user.id,
            consent_type=ConsentType.MEDICAL_DISCLAIMER,
            version=CONSENT_VERSION,
            accepted=payload.accepted_medical_disclaimer,
        )
    )

    current_user.onboarding_completed = True
    db.add(current_user)
    db.commit()

    return OnboardingResponse(onboarding_completed=True)
