from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.food import Food
from app.models.meal import DEFAULT_MEAL_CATEGORY_NAMES, MealCategory, MealLog, MealLogItem
from app.schemas.meal import MealLogCreate


def ensure_default_categories(db: Session, user_id: int) -> list[MealCategory]:
    existing = list(
        db.execute(select(MealCategory).where(MealCategory.user_id == user_id)).scalars()
    )
    if existing:
        return existing

    categories = [
        MealCategory(user_id=user_id, name=name, sort_order=idx)
        for idx, name in enumerate(DEFAULT_MEAL_CATEGORY_NAMES)
    ]
    db.add_all(categories)
    db.flush()
    return categories


def _snapshot_item(food: Food, quantity_g: float) -> dict:
    factor = quantity_g / 100.0
    return {
        "kcal": food.kcal_per_100g * factor,
        "protein_g": food.protein_g_per_100g * factor,
        "carbs_g": food.carbs_g_per_100g * factor,
        "fat_g": food.fat_g_per_100g * factor,
        "fiber_g": food.fiber_g_per_100g * factor if food.fiber_g_per_100g is not None else None,
        "sodium_mg": food.sodium_mg_per_100g * factor if food.sodium_mg_per_100g is not None else None,
        "sugar_g": food.sugar_g_per_100g * factor if food.sugar_g_per_100g is not None else None,
    }


def log_meal(db: Session, user_id: int, payload: MealLogCreate) -> MealLog:
    food_ids = [item.food_id for item in payload.items]
    foods = {f.id: f for f in db.execute(select(Food).where(Food.id.in_(food_ids))).scalars()}

    meal_log = MealLog(
        user_id=user_id,
        meal_category_id=payload.meal_category_id,
        logged_at=payload.logged_at,
    )
    db.add(meal_log)
    db.flush()

    for item in payload.items:
        food = foods[item.food_id]
        db.add(
            MealLogItem(
                meal_log_id=meal_log.id,
                food_id=food.id,
                quantity_g=item.quantity_g,
                **_snapshot_item(food, item.quantity_g),
            )
        )

    db.commit()
    db.refresh(meal_log)
    return meal_log
