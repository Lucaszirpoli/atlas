"""Academia da pessoa + check-in com prova de localização (desafio "quem vai
mais à academia"). Ver app/models/gym.py e app/services/gym_service.py."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.gym import HOME_GYM_RADIUS_M, GymCheckIn, UserGym
from app.models.user import User
from app.services import gym_service

router = APIRouter(prefix="/gyms", tags=["gyms"])


class GymSearchResult(BaseModel):
    name: str
    address: str | None
    lat: float
    lng: float
    osm_id: str | None
    distance_m: float


class GymRead(BaseModel):
    name: str
    address: str | None
    lat: float
    lng: float
    osm_id: str | None

    model_config = {"from_attributes": True}


class CheckInRequest(BaseModel):
    lat: float
    lng: float
    # Nome informado quando a pessoa treinou em OUTRA academia (fora da dela).
    gym_name: str | None = None


class CheckInRead(BaseModel):
    day: date
    at_home_gym: bool
    distance_m: float | None
    gym_name: str | None

    model_config = {"from_attributes": True}


@router.get("/search", response_model=list[GymSearchResult])
def search(
    q: str,
    lat: float,
    lng: float,
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Busca academias pelo nome perto de você (OpenStreetMap). Requer a
    localização atual pra limitar a busca à sua região."""
    return gym_service.search_gyms(q, lat, lng)


@router.get("/me", response_model=GymRead | None)
def get_my_gym(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserGym | None:
    return db.execute(select(UserGym).where(UserGym.user_id == current_user.id)).scalar_one_or_none()


@router.put("/me", response_model=GymRead)
def set_my_gym(
    payload: GymRead,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserGym:
    """Cadastra/troca a academia da pessoa (a que ela escolheu na busca)."""
    gym = db.execute(select(UserGym).where(UserGym.user_id == current_user.id)).scalar_one_or_none()
    if gym is None:
        gym = UserGym(user_id=current_user.id)
        db.add(gym)
    gym.name = payload.name
    gym.address = payload.address
    gym.lat = payload.lat
    gym.lng = payload.lng
    gym.osm_id = payload.osm_id
    db.commit()
    db.refresh(gym)
    return gym


@router.post("/checkin", response_model=CheckInRead)
def check_in(
    payload: CheckInRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GymCheckIn:
    """Marca que treinou hoje, provando pela localização. Perto da academia
    cadastrada = check-in normal; longe = conta, mas marcado como "fora"
    (quem viajou não perde o dia, e o desafio mostra a verdade). Um por dia."""
    gym = db.execute(select(UserGym).where(UserGym.user_id == current_user.id)).scalar_one_or_none()
    if gym is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cadastre sua academia antes de fazer check-in.",
        )

    today = datetime.now(timezone.utc).date()
    existing = db.execute(
        select(GymCheckIn).where(GymCheckIn.user_id == current_user.id, GymCheckIn.day == today)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Você já fez check-in hoje."
        )

    dist = gym_service.haversine_m(payload.lat, payload.lng, gym.lat, gym.lng)
    at_home = dist <= HOME_GYM_RADIUS_M
    if not at_home and not (payload.gym_name or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Você está longe da sua academia. Se treinou em outro lugar, "
                "informe o nome da academia pra registrar como treino fora."
            ),
        )

    checkin = GymCheckIn(
        user_id=current_user.id,
        day=today,
        lat=payload.lat,
        lng=payload.lng,
        at_home_gym=at_home,
        distance_m=round(dist, 1),
        gym_name=gym.name if at_home else (payload.gym_name or "").strip()[:150],
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


@router.get("/checkins", response_model=list[CheckInRead])
def my_checkins(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GymCheckIn]:
    rows = list(
        db.execute(
            select(GymCheckIn)
            .where(GymCheckIn.user_id == current_user.id)
            .order_by(GymCheckIn.day.desc())
            .limit(max(1, min(days, 365)))
        ).scalars()
    )
    return rows
