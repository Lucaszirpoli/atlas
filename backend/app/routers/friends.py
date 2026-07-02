from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.friend_request import FriendRequest, FriendRequestStatus
from app.models.user import User
from app.schemas.friend import FriendRequestCreate, FriendRequestRead, UserSummary
from app.services import friend_service, user_service

router = APIRouter(prefix="/friends", tags=["friends"])


@router.post("/request", response_model=FriendRequestRead, status_code=status.HTTP_201_CREATED)
def send_friend_request(
    payload: FriendRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    addressee = user_service.get_by_handle(db, payload.handle)
    if addressee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    if addressee.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode adicionar a si mesmo"
        )
    try:
        request = friend_service.send_or_accept_request(db, current_user.id, addressee)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return {
        "id": request.id,
        "status": request.status,
        "created_at": request.created_at,
        "other_user": addressee,
        "direction": "sent",
    }


@router.get("/requests", response_model=list[FriendRequestRead])
def list_pending_requests(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    rows = list(
        db.execute(
            select(FriendRequest).where(
                FriendRequest.status == FriendRequestStatus.PENDING,
                or_(
                    FriendRequest.requester_id == current_user.id,
                    FriendRequest.addressee_id == current_user.id,
                ),
            )
        ).scalars()
    )
    result = []
    for r in rows:
        is_sent = r.requester_id == current_user.id
        other_id = r.addressee_id if is_sent else r.requester_id
        other = db.get(User, other_id)
        result.append(
            {
                "id": r.id,
                "status": r.status,
                "created_at": r.created_at,
                "other_user": other,
                "direction": "sent" if is_sent else "received",
            }
        )
    return result


@router.post("/requests/{request_id}/accept", response_model=FriendRequestRead)
def accept_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    from datetime import datetime, timezone

    request = db.get(FriendRequest, request_id)
    if request is None or request.addressee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    request.status = FriendRequestStatus.ACCEPTED
    request.responded_at = datetime.now(timezone.utc)
    db.commit()
    other = db.get(User, request.requester_id)
    return {
        "id": request.id,
        "status": request.status,
        "created_at": request.created_at,
        "other_user": other,
        "direction": "received",
    }


@router.post("/requests/{request_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    from datetime import datetime, timezone

    request = db.get(FriendRequest, request_id)
    if request is None or request.addressee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    request.status = FriendRequestStatus.DECLINED
    request.responded_at = datetime.now(timezone.utc)
    db.commit()


@router.get("", response_model=list[UserSummary])
def list_friends(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[User]:
    friend_ids = friend_service.get_friend_ids(db, current_user.id)
    if not friend_ids:
        return []
    return list(db.execute(select(User).where(User.id.in_(friend_ids))).scalars())
