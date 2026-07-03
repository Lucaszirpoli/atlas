from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.food import Food
from app.models.meal import MealCategory, MealLog, MealLogItem
from app.models.saved_meal import SavedMeal, SavedMealItem
from app.models.user import User
from app.schemas.meal import (
    MealCategoryCreate,
    MealCategoryRead,
    MealCategoryUpdate,
    MealLogCreate,
    MealLogRead,
    SavedMealCreate,
    SavedMealRead,
)
from app.services import meal_service

router = APIRouter(prefix="/meals", tags=["meals"])


@router.get("/categories", response_model=list[MealCategoryRead])
def list_categories(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[MealCategory]:
    categories = meal_service.ensure_default_categories(db, current_user.id)
    db.commit()
    return sorted(categories, key=lambda c: c.sort_order)


@router.post("/categories", response_model=MealCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: MealCategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MealCategory:
    max_order = db.execute(
        select(MealCategory.sort_order)
        .where(MealCategory.user_id == current_user.id)
        .order_by(MealCategory.sort_order.desc())
        .limit(1)
    ).scalar_one_or_none()
    category = MealCategory(
        user_id=current_user.id, name=payload.name, sort_order=(max_order or 0) + 1
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=MealCategoryRead)
def rename_category(
    category_id: int,
    payload: MealCategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MealCategory:
    category = db.get(MealCategory, category_id)
    if category is None or category.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
    category.name = payload.name
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    category = db.get(MealCategory, category_id)
    if category is None or category.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
    db.delete(category)
    db.commit()


@router.post("", response_model=MealLogRead, status_code=status.HTTP_201_CREATED)
def log_meal(
    payload: MealLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MealLog:
    category = db.get(MealCategory, payload.meal_category_id)
    if category is None or category.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")

    food_ids = [item.food_id for item in payload.items]
    found = set(db.execute(select(Food.id).where(Food.id.in_(food_ids))).scalars())
    missing = set(food_ids) - found
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Alimentos não encontrados: {missing}"
        )

    return meal_service.log_meal(db, current_user.id, payload)


@router.get("", response_model=list[MealLogRead])
def list_meals_for_day(
    day: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MealLog]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)
    stmt = (
        select(MealLog)
        .options(selectinload(MealLog.items).selectinload(MealLogItem.food))
        .where(
            MealLog.user_id == current_user.id,
            MealLog.logged_at >= start,
            MealLog.logged_at <= end,
        )
        .order_by(MealLog.logged_at)
    )
    return list(db.execute(stmt).scalars())


@router.get("/saved", response_model=list[SavedMealRead])
def list_saved_meals(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SavedMeal]:
    stmt = (
        select(SavedMeal)
        .options(selectinload(SavedMeal.items).selectinload(SavedMealItem.food))
        .where(SavedMeal.user_id == current_user.id)
    )
    return list(db.execute(stmt).scalars())


@router.post("/saved", response_model=SavedMealRead, status_code=status.HTTP_201_CREATED)
def create_saved_meal(
    payload: SavedMealCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SavedMeal:
    saved_meal = SavedMeal(user_id=current_user.id, name=payload.name)
    db.add(saved_meal)
    db.flush()
    for item in payload.items:
        db.add(
            SavedMealItem(
                saved_meal_id=saved_meal.id, food_id=item.food_id, quantity_g=item.quantity_g
            )
        )
    db.commit()
    db.refresh(saved_meal)
    return saved_meal


@router.delete("/{meal_log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal_log(
    meal_log_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    meal_log = db.get(MealLog, meal_log_id)
    if meal_log is None or meal_log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refeição não encontrada")
    db.delete(meal_log)
    db.commit()
