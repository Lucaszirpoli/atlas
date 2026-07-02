from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.challenge import Challenge, ChallengeParticipant
from app.models.user import User
from app.schemas.challenge import ChallengeCreate, ChallengeLeaderboard, ChallengeRead
from app.services import challenge_service, user_service

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.post("", response_model=ChallengeRead, status_code=status.HTTP_201_CREATED)
def create_challenge(
    payload: ChallengeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Challenge:
    challenge = Challenge(
        creator_id=current_user.id,
        name=payload.name,
        metric=payload.metric,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(challenge)
    db.flush()
    db.add(ChallengeParticipant(challenge_id=challenge.id, user_id=current_user.id))
    for handle in payload.invite_handles:
        user = user_service.get_by_handle(db, handle)
        if user is not None:
            db.add(ChallengeParticipant(challenge_id=challenge.id, user_id=user.id))
    db.commit()
    db.refresh(challenge)
    return challenge


@router.get("", response_model=list[ChallengeRead])
def list_my_challenges(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Challenge]:
    stmt = (
        select(Challenge)
        .join(ChallengeParticipant, ChallengeParticipant.challenge_id == Challenge.id)
        .where(ChallengeParticipant.user_id == current_user.id)
    )
    return list(db.execute(stmt).scalars())


@router.post("/{challenge_id}/join", status_code=status.HTTP_204_NO_CONTENT)
def join_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    challenge = db.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Desafio não encontrado")
    existing = db.execute(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == challenge_id,
            ChallengeParticipant.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(ChallengeParticipant(challenge_id=challenge_id, user_id=current_user.id))
        db.commit()


@router.get("/{challenge_id}/leaderboard", response_model=ChallengeLeaderboard)
def get_leaderboard(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    challenge = db.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Desafio não encontrado")
    entries = challenge_service.build_leaderboard(db, challenge)
    return {
        "challenge": challenge,
        "entries": [{"user": db.get(User, e["user_id"]), "value": e["value"]} for e in entries],
    }
