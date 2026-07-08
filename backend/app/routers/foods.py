from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.food import Food, FoodSource
from app.models.saved_meal import FavoriteFood
from app.models.user import User
from app.schemas.food import FoodCreate, FoodRead
from app.services import food_service

router = APIRouter(prefix="/foods", tags=["foods"])


@router.get("/search", response_model=list[FoodRead])
def search_foods(q: str, db: Session = Depends(get_db)) -> list[Food]:
    """Busca local (rápida, sem acento) — retorna na hora enquanto a pessoa
    digita. As marcas de outros países vêm por /search/brands em separado."""
    if len(q.strip()) < 2:
        return []
    return food_service.search_local(db, q.strip())


@router.get("/search/brands", response_model=list[FoodRead])
def search_food_brands(q: str, db: Session = Depends(get_db)) -> list[Food]:
    """Busca ao vivo de marcas no Open Food Facts (cacheia o que voltar). É
    mais lenta (rede), então o app chama depois da busca local e encaixa os
    resultados conforme chegam."""
    if len(q.strip()) < 2:
        return []
    return food_service.search_brands_live(db, q.strip())


@router.get("/barcode/{barcode}", response_model=FoodRead)
def get_food_by_barcode(barcode: str, db: Session = Depends(get_db)) -> Food:
    food = food_service.get_by_barcode(db, barcode)
    if food is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado. Você pode cadastrá-lo manualmente.",
        )
    return food


@router.post("", response_model=FoodRead, status_code=status.HTTP_201_CREATED)
def create_custom_food(
    payload: FoodCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Food:
    food = Food(
        source=FoodSource.CUSTOM,
        created_by_user_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(food)
    db.commit()
    db.refresh(food)
    return food


@router.get("/favorites", response_model=list[FoodRead])
def list_favorites(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Food]:
    stmt = (
        select(Food)
        .join(FavoriteFood, FavoriteFood.food_id == Food.id)
        .where(FavoriteFood.user_id == current_user.id)
    )
    return list(db.execute(stmt).scalars())


@router.post("/{food_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    existing = db.execute(
        select(FavoriteFood).where(
            FavoriteFood.user_id == current_user.id, FavoriteFood.food_id == food_id
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(FavoriteFood(user_id=current_user.id, food_id=food_id))
        db.commit()


@router.delete("/{food_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    existing = db.execute(
        select(FavoriteFood).where(
            FavoriteFood.user_id == current_user.id, FavoriteFood.food_id == food_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.commit()
