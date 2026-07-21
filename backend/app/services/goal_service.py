from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calorie_goal import CalorieGoal, GoalMode
from app.models.user_profile import UserProfile
from app.models.weight_log import WeightLog
from app.services.nutrition_calc import compute_auto_goal

SIGNIFICANT_KCAL_DELTA = 100


def get_current_goal(db: Session, user_id: int) -> CalorieGoal | None:
    return db.execute(
        select(CalorieGoal)
        .where(CalorieGoal.user_id == user_id)
        .order_by(CalorieGoal.created_at.desc(), CalorieGoal.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_latest_weight_kg(db: Session, user_id: int) -> float | None:
    log = db.execute(
        select(WeightLog)
        .where(WeightLog.user_id == user_id)
        .order_by(WeightLog.recorded_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return log.weight_kg if log else None


def compute_suggestion(db: Session, user_id: int, profile: UserProfile) -> dict:
    weight_kg = get_latest_weight_kg(db, user_id)
    if weight_kg is None:
        raise ValueError("Usuário ainda não tem peso registrado")

    suggestion = compute_auto_goal(
        biological_sex=profile.biological_sex,
        weight_kg=weight_kg,
        height_cm=profile.height_cm,
        age=profile.age,
        activity_level=profile.activity_level,
        goal=profile.goal,
    )

    current = get_current_goal(db, user_id)
    changed_significantly = (
        current is None or abs(current.kcal - suggestion["kcal"]) >= SIGNIFICANT_KCAL_DELTA
    )

    return {**suggestion, "current_goal": current, "changed_significantly": changed_significantly}


def apply_auto_goal(db: Session, user_id: int, suggestion: dict) -> CalorieGoal:
    goal = CalorieGoal(
        user_id=user_id,
        mode=GoalMode.AUTO,
        kcal=suggestion["kcal"],
        protein_g=suggestion["protein_g"],
        carbs_g=suggestion["carbs_g"],
        fat_g=suggestion["fat_g"],
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def apply_manual_goal(db: Session, user_id: int, payload) -> CalorieGoal:
    goal = CalorieGoal(
        user_id=user_id,
        mode=GoalMode.MANUAL,
        kcal=payload.kcal,
        protein_g=payload.protein_g,
        carbs_g=payload.carbs_g,
        fat_g=payload.fat_g,
        fiber_g=payload.fiber_g,
        sodium_mg=payload.sodium_mg,
        sugar_g=payload.sugar_g,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal
