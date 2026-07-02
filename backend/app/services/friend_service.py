from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.block import BlockedUser
from app.models.friend_request import FriendRequest, FriendRequestStatus
from app.models.user import User


def get_friend_ids(db: Session, user_id: int) -> set[int]:
    rows = db.execute(
        select(FriendRequest).where(
            FriendRequest.status == FriendRequestStatus.ACCEPTED,
            or_(FriendRequest.requester_id == user_id, FriendRequest.addressee_id == user_id),
        )
    ).scalars()
    return {
        (r.addressee_id if r.requester_id == user_id else r.requester_id) for r in rows
    }


def are_friends(db: Session, user_a: int, user_b: int) -> bool:
    return user_b in get_friend_ids(db, user_a)


def is_blocked_either_way(db: Session, user_a: int, user_b: int) -> bool:
    row = db.execute(
        select(BlockedUser).where(
            or_(
                (BlockedUser.user_id == user_a) & (BlockedUser.blocked_user_id == user_b),
                (BlockedUser.user_id == user_b) & (BlockedUser.blocked_user_id == user_a),
            )
        )
    ).scalar_one_or_none()
    return row is not None


def send_or_accept_request(db: Session, requester_id: int, addressee: User) -> FriendRequest:
    if is_blocked_either_way(db, requester_id, addressee.id):
        raise ValueError("Não é possível enviar pedido de amizade para esse usuário")

    existing_reverse = db.execute(
        select(FriendRequest).where(
            FriendRequest.requester_id == addressee.id,
            FriendRequest.addressee_id == requester_id,
            FriendRequest.status == FriendRequestStatus.PENDING,
        )
    ).scalar_one_or_none()
    if existing_reverse is not None:
        from datetime import datetime, timezone

        existing_reverse.status = FriendRequestStatus.ACCEPTED
        existing_reverse.responded_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing_reverse)
        return existing_reverse

    existing = db.execute(
        select(FriendRequest).where(
            FriendRequest.requester_id == requester_id, FriendRequest.addressee_id == addressee.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    request = FriendRequest(requester_id=requester_id, addressee_id=addressee.id)
    db.add(request)
    db.commit()
    db.refresh(request)
    return request
