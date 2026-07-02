from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.block import BlockedUser
from app.models.user import User
from app.schemas.friend import UserSummary
from app.services import user_service

router = APIRouter(prefix="/blocks", tags=["blocks"])


class BlockCreate(BaseModel):
    handle: str = Field(min_length=3, max_length=30)


@router.get("", response_model=list[UserSummary])
def list_blocked(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[User]:
    blocked_ids = db.execute(
        select(BlockedUser.blocked_user_id).where(BlockedUser.user_id == current_user.id)
    ).scalars()
    ids = list(blocked_ids)
    if not ids:
        return []
    return list(db.execute(select(User).where(User.id.in_(ids))).scalars())


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def block_user(
    payload: BlockCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    target = user_service.get_by_handle(db, payload.handle)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    existing = db.execute(
        select(BlockedUser).where(
            BlockedUser.user_id == current_user.id, BlockedUser.blocked_user_id == target.id
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(BlockedUser(user_id=current_user.id, blocked_user_id=target.id))
        db.commit()


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unblock_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    existing = db.execute(
        select(BlockedUser).where(
            BlockedUser.user_id == current_user.id, BlockedUser.blocked_user_id == user_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.commit()
