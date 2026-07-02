from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.feed import FeedPost
from app.models.user import User
from app.schemas.feed import (
    FeedCommentCreate,
    FeedCommentRead,
    FeedPostRead,
    FeedReactionCreate,
    ShareMealRequest,
    ShareProgressPhotoRequest,
)
from app.services import feed_service

router = APIRouter(prefix="/feed", tags=["feed"])


def _serialize_post(db: Session, post: FeedPost, current_user_id: int) -> dict:
    my_reaction = next((r.emoji for r in post.reactions if r.user_id == current_user_id), None)
    return {
        "id": post.id,
        "author": post.user,
        "post_type": post.post_type,
        "reference_id": post.reference_id,
        "caption": post.caption,
        "created_at": post.created_at,
        "summary": feed_service.build_post_summary(db, post),
        "reaction_count": len(post.reactions),
        "my_reaction": my_reaction,
        "comments": [
            {"id": c.id, "author": c.user, "content": c.content, "created_at": c.created_at}
            for c in post.comments
        ],
    }


@router.get("", response_model=list[FeedPostRead])
def get_feed(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    posts = feed_service.list_feed(db, current_user.id)
    return [_serialize_post(db, p, current_user.id) for p in posts]


@router.post("/share-meal", response_model=FeedPostRead, status_code=status.HTTP_201_CREATED)
def share_meal(
    payload: ShareMealRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        post = feed_service.create_meal_post(db, current_user.id, payload.meal_log_id, payload.caption)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_post(db, post, current_user.id)


@router.post(
    "/share-progress-photo", response_model=FeedPostRead, status_code=status.HTTP_201_CREATED
)
def share_progress_photo(
    payload: ShareProgressPhotoRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        post = feed_service.create_progress_photo_post(
            db, current_user.id, payload.progress_photo_id, payload.caption
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_post(db, post, current_user.id)


@router.post("/{post_id}/react", status_code=status.HTTP_204_NO_CONTENT)
def react_to_post(
    post_id: int,
    payload: FeedReactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    feed_service.react(db, post_id, current_user.id, payload.emoji)


@router.delete("/{post_id}/react", status_code=status.HTTP_204_NO_CONTENT)
def unreact_to_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    feed_service.remove_reaction(db, post_id, current_user.id)


@router.post("/{post_id}/comments", response_model=FeedCommentRead, status_code=status.HTTP_201_CREATED)
def comment_on_post(
    post_id: int,
    payload: FeedCommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    comment = feed_service.add_comment(db, post_id, current_user.id, payload.content)
    return {
        "id": comment.id,
        "author": current_user,
        "content": comment.content,
        "created_at": comment.created_at,
    }
