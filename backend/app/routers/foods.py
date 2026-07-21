from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.food import Food, FoodPortion, FoodSource
from app.models.saved_meal import FavoriteFood
from app.models.user import User
from app.schemas.food import FoodCreate, FoodPortionCreate, FoodPortionRead, FoodRead
from app.services import food_service

router = APIRouter(prefix="/foods", tags=["foods"])


def _portion_read(p: FoodPortion) -> dict:
    return {"id": p.id, "label": p.label, "grams": p.grams, "is_custom": p.created_by_user_id is not None}


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


# --- Medidas caseiras (gramas/unidades) -----------------------------------
# Cada alimento pode ser registrado em gramas OU por uma medida caseira nomeada
# (unidade, fatia, colher, concha). "gramas" é sempre a opção base no app e não
# é uma FoodPortion — só as medidas nomeadas ficam aqui.


@router.get("/{food_id}/portions", response_model=list[FoodPortionRead])
def list_food_portions(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Medidas do alimento: as embutidas (created_by_user_id nulo, visíveis pra
    todos) + as personalizadas DESTE usuário. Nunca as de outros usuários."""
    portions = list(
        db.execute(
            select(FoodPortion)
            .where(
                FoodPortion.food_id == food_id,
                (FoodPortion.created_by_user_id.is_(None))
                | (FoodPortion.created_by_user_id == current_user.id),
            )
            .order_by(FoodPortion.created_by_user_id.isnot(None), FoodPortion.sort_order, FoodPortion.id)
        ).scalars()
    )
    return [_portion_read(p) for p in portions]


@router.post("/{food_id}/portions", response_model=FoodPortionRead, status_code=status.HTTP_201_CREATED)
def create_food_portion(
    food_id: int,
    payload: FoodPortionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Cria uma medida personalizada do usuário pra este alimento ("meu pão =
    65g"). Só o dono vê e pode apagar."""
    food = db.get(Food, food_id)
    if food is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alimento não encontrado")

    label = payload.label.strip()
    # Evita duplicar uma medida que o usuário já criou com o mesmo nome.
    existing = db.execute(
        select(FoodPortion).where(
            FoodPortion.food_id == food_id,
            FoodPortion.created_by_user_id == current_user.id,
            func.lower(FoodPortion.label) == label.lower(),
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.grams = payload.grams
        db.commit()
        db.refresh(existing)
        return _portion_read(existing)

    portion = FoodPortion(
        food_id=food_id,
        label=label,
        grams=payload.grams,
        created_by_user_id=current_user.id,
        sort_order=100,
    )
    db.add(portion)
    db.commit()
    db.refresh(portion)
    return _portion_read(portion)


@router.delete("/{food_id}/portions/{portion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food_portion(
    food_id: int,
    portion_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Apaga uma medida personalizada do próprio usuário. As embutidas (sem
    dono) não podem ser apagadas — 404 pra não vazar que existem doutros donos."""
    portion = db.get(FoodPortion, portion_id)
    if (
        portion is None
        or portion.food_id != food_id
        or portion.created_by_user_id != current_user.id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medida não encontrada")
    db.delete(portion)
    db.commit()
