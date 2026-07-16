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
from app.schemas.profile import ProfileCalcRead, ProfileCalcUpdate
from app.schemas.user import HandleAvailabilityResponse, UserRead
from app.services import goal_service, user_service

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


def _require_profile(current_user: User) -> UserProfile:
    if current_user.profile is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onboarding precisa ser concluído antes de editar o perfil",
        )
    return current_user.profile


@router.get("/profile/calc", response_model=ProfileCalcRead)
def read_profile_calc(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ProfileCalcRead:
    profile = _require_profile(current_user)
    return ProfileCalcRead(
        biological_sex=profile.biological_sex,
        age=profile.age,
        height_cm=profile.height_cm,
        activity_level=profile.activity_level,
        goal=profile.goal,
        current_weight_kg=goal_service.get_latest_weight_kg(db, current_user.id),
    )


@router.patch("/profile/calc", response_model=ProfileCalcRead)
def update_profile_calc(
    payload: ProfileCalcUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileCalcRead:
    profile = _require_profile(current_user)

    if payload.biological_sex is not None:
        profile.biological_sex = payload.biological_sex
    if payload.age is not None:
        profile.age = payload.age
    if payload.height_cm is not None:
        profile.height_cm = payload.height_cm
    if payload.activity_level is not None:
        profile.activity_level = payload.activity_level
    if payload.goal is not None:
        profile.goal = payload.goal

    # Peso é histórico append-only: um novo valor vira um novo registro, nunca
    # sobrescreve o anterior (base dos gráficos de evolução).
    if payload.current_weight_kg is not None:
        db.add(
            WeightLog(
                user_id=current_user.id,
                weight_kg=payload.current_weight_kg,
                recorded_at=datetime.now(timezone.utc),
            )
        )

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return ProfileCalcRead(
        biological_sex=profile.biological_sex,
        age=profile.age,
        height_cm=profile.height_cm,
        activity_level=profile.activity_level,
        goal=profile.goal,
        current_weight_kg=goal_service.get_latest_weight_kg(db, current_user.id),
    )


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

    # Já cria a meta de calorias/macros automática (Mifflin) a partir dos dados
    # do onboarding — sem isso, a pessoa terminava o cadastro SEM meta, e o
    # dashboard/dieta ficavam sem kcal do dia até ela abrir a tela de meta
    # (inconsistente: dava pra gerar/aplicar dieta sem ter meta definida).
    from app.models.calorie_goal import CalorieGoal, GoalMode
    from app.services.nutrition_calc import compute_auto_goal

    auto = compute_auto_goal(
        biological_sex=payload.biological_sex,
        weight_kg=payload.current_weight_kg,
        height_cm=payload.height_cm,
        age=payload.age,
        activity_level=payload.activity_level,
        goal=payload.goal,
    )
    db.add(
        CalorieGoal(
            user_id=current_user.id,
            mode=GoalMode.AUTO,
            kcal=auto["kcal"],
            protein_g=auto["protein_g"],
            carbs_g=auto["carbs_g"],
            fat_g=auto["fat_g"],
        )
    )

    current_user.onboarding_completed = True
    db.add(current_user)
    db.commit()

    return OnboardingResponse(onboarding_completed=True)
