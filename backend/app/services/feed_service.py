from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from app.models.body_measurement import ProgressPhoto
from app.models.feed import FeedComment, FeedPost, FeedPostType, FeedReaction
from app.models.meal import MealCategory, MealLog, MealLogItem
from app.models.privacy_settings import UserPrivacySettings
from app.models.workout_session import WorkoutSession
from app.services import friend_service


def get_or_create_privacy(db: Session, user_id: int) -> UserPrivacySettings:
    settings = db.execute(
        select(UserPrivacySettings).where(UserPrivacySettings.user_id == user_id)
    ).scalar_one_or_none()
    if settings is None:
        settings = UserPrivacySettings(user_id=user_id)
        db.add(settings)
        db.flush()
    return settings


def maybe_create_workout_post(db: Session, session: WorkoutSession) -> FeedPost | None:
    privacy = get_or_create_privacy(db, session.user_id)
    if not privacy.share_workouts:
        return None
    post = FeedPost(user_id=session.user_id, post_type=FeedPostType.WORKOUT, reference_id=session.id)
    db.add(post)
    db.flush()
    return post


def create_meal_post(db: Session, user_id: int, meal_log_id: int, caption: str | None) -> FeedPost:
    meal_log = db.get(MealLog, meal_log_id)
    if meal_log is None or meal_log.user_id != user_id:
        raise ValueError("Refeição não encontrada")
    post = FeedPost(
        user_id=user_id, post_type=FeedPostType.MEAL, reference_id=meal_log_id, caption=caption
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def create_progress_photo_post(
    db: Session, user_id: int, progress_photo_id: int, caption: str | None
) -> FeedPost:
    photo = db.get(ProgressPhoto, progress_photo_id)
    if photo is None or photo.user_id != user_id:
        raise ValueError("Foto não encontrada")
    post = FeedPost(
        user_id=user_id,
        post_type=FeedPostType.PROGRESS_PHOTO,
        reference_id=progress_photo_id,
        caption=caption,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def build_post_summary(db: Session, post: FeedPost) -> dict:
    if post.post_type == FeedPostType.WORKOUT:
        session = db.get(WorkoutSession, post.reference_id)
        if session is None:
            return {}
        volume = sum(s.weight_kg * s.reps for s in session.sets)
        duration = (
            int((session.completed_at - session.started_at).total_seconds())
            if session.completed_at
            else 0
        )
        return {"volume_total_kg": volume, "duration_seconds": duration}

    if post.post_type == FeedPostType.MEAL:
        meal_log = db.execute(
            select(MealLog)
            .options(selectinload(MealLog.items))
            .where(MealLog.id == post.reference_id)
        ).scalar_one_or_none()
        if meal_log is None:
            return {}
        category = db.get(MealCategory, meal_log.meal_category_id)
        return {
            "categoria": category.name if category else None,
            "kcal_total": sum(i.kcal for i in meal_log.items),
        }

    if post.post_type == FeedPostType.PROGRESS_PHOTO:
        photo = db.get(ProgressPhoto, post.reference_id)
        return {"photo_url": photo.photo_url} if photo else {}

    return {}


def list_feed(db: Session, user_id: int, limit: int = 50) -> list[FeedPost]:
    friend_ids = friend_service.get_friend_ids(db, user_id)
    visible_user_ids = friend_ids | {user_id}
    blocked_excluded = {
        uid for uid in visible_user_ids if not friend_service.is_blocked_either_way(db, user_id, uid)
    }

    stmt = (
        select(FeedPost)
        .options(selectinload(FeedPost.reactions), selectinload(FeedPost.comments))
        .where(FeedPost.user_id.in_(blocked_excluded))
        .order_by(FeedPost.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def react(db: Session, post_id: int, user_id: int, emoji: str) -> FeedReaction:
    existing = db.execute(
        select(FeedReaction).where(FeedReaction.post_id == post_id, FeedReaction.user_id == user_id)
    ).scalar_one_or_none()
    if existing is not None:
        existing.emoji = emoji
        db.commit()
        db.refresh(existing)
        return existing
    reaction = FeedReaction(post_id=post_id, user_id=user_id, emoji=emoji)
    db.add(reaction)
    db.commit()
    db.refresh(reaction)
    return reaction


def remove_reaction(db: Session, post_id: int, user_id: int) -> None:
    existing = db.execute(
        select(FeedReaction).where(FeedReaction.post_id == post_id, FeedReaction.user_id == user_id)
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.commit()


def add_comment(db: Session, post_id: int, user_id: int, content: str) -> FeedComment:
    comment = FeedComment(post_id=post_id, user_id=user_id, content=content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment
