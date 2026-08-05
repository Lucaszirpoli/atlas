from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.usertime import resolve_tz
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.weight_log import WeightLog
from app.schemas.profile import ProfileCalcRead, ProfileCalcUpdate, TimezoneUpdate
from app.schemas.user import HandleAvailabilityResponse, ResetDataResponse, UserRead
from app.services import goal_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


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


@router.put("/timezone", status_code=status.HTTP_204_NO_CONTENT)
def set_timezone(
    payload: TimezoneUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """O app informa o fuso do aparelho ao entrar. É o que define QUE DIA de
    calendário é cada registro pra esta pessoa (ver core/usertime.py) — sem
    isso o backend fatiava tudo em UTC e o que era registrado à noite caía no
    dia seguinte. Silencioso: se o perfil ainda não existe (pré-onboarding),
    não é erro — o padrão do produto cobre até lá."""
    profile = current_user.profile
    if profile is None:
        return
    tz = str(resolve_tz(payload.timezone).key)
    if profile.timezone != tz:
        profile.timezone = tz
        db.add(profile)
        db.commit()


@router.post("/reset-data", response_model=ResetDataResponse)
def reset_data(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ResetDataResponse:
    """Apaga TODO o histórico da pessoa, mantendo a conta e o login.

    Por que existe: a regra 4 do projeto (histórico append-only) protege o dado
    de ser sobrescrito por um UPDATE — ela não obriga a pessoa a conviver com um
    começo bagunçado. Quem testou o app por semanas antes de começar pra valer
    fica com gráficos que descrevem os testes, não a vida dela, e não tinha
    saída a não ser criar outra conta.

    O que NÃO sai: a conta, o e-mail, o plano (Pro continua Pro), os
    consentimentos LGPD (são registro legal de uma escolha que ela fez — apagar
    o consentimento não é limpar dado, é perder a prova) e as rotinas
    arquivadas... não: rotinas saem também, ver abaixo. O que fica é só conta,
    plano e consentimento.
    """
    from app.models.body_measurement import BodyMeasurement, ProgressPhoto
    from app.models.calorie_goal import CalorieGoal
    from app.models.coaching_action import CoachingAction
    from app.models.coaching_adjustment import CoachingAdjustment
    from app.models.coaching_baseline import CoachingBaseline
    from app.models.coaching_plan import CoachingPlan, QuestionnaireDraft
    from app.models.coaching_technique_cue import CoachingTechniqueCue
    from app.models.coaching_transition import CoachingTransition
    from app.models.day_quality import NutritionDayMark
    from app.models.exercise_history_link import ExerciseHistoryLink
    from app.models.meal import MealLog
    from app.models.routine import Routine
    from app.models.sleep_log import SleepLog
    from app.models.water_log import WaterLog
    from app.models.workout_session import WorkoutSession

    uid = current_user.id
    apagados: dict[str, int] = {}

    # MealLog / WorkoutSession / Routine saem pelo ORM (um a um) porque têm
    # filhos em cascade (itens da refeição, séries da sessão, exercícios da
    # rotina): um DELETE em massa por query não dispara a cascade do ORM e
    # deixaria os filhos órfãos.
    for rotulo, modelo in (
        ("refeições", MealLog),
        ("treinos", WorkoutSession),
        ("rotinas", Routine),
    ):
        linhas = list(db.execute(select(modelo).where(modelo.user_id == uid)).scalars())
        for linha in linhas:
            db.delete(linha)
        apagados[rotulo] = len(linhas)

    # O resto não tem filhos — delete direto por query é seguro e barato.
    for rotulo, modelo in (
        ("peso", WeightLog),
        ("sono", SleepLog),
        ("água", WaterLog),
        ("medidas", BodyMeasurement),
        ("fotos", ProgressPhoto),
        ("metas", CalorieGoal),
        ("dias marcados", NutritionDayMark),
        ("planos do coach", CoachingPlan),
        ("rascunho do questionário", QuestionnaireDraft),
        ("ações do coach", CoachingAction),
        ("ajustes do coach", CoachingAdjustment),
        ("marcos do coach", CoachingBaseline),
        ("técnicas do coach", CoachingTechniqueCue),
        ("transições do coach", CoachingTransition),
        ("heranças de exercício", ExerciseHistoryLink),
    ):
        apagados[rotulo] = int(
            db.execute(delete(modelo).where(modelo.user_id == uid)).rowcount or 0
        )

    # O perfil volta pro estado "nunca respondeu": sem isso a pessoa apagaria a
    # história mas continuaria com o plano montado em cima dela.
    if current_user.profile is not None:
        db.delete(current_user.profile)
        apagados["perfil"] = 1
    current_user.onboarding_completed = False
    db.add(current_user)

    db.commit()
    apagados = {k: v for k, v in apagados.items() if v}
    return ResetDataResponse(apagados=apagados, total=sum(apagados.values()))
