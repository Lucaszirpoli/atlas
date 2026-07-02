from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.food import Food, FoodSource
from app.services import open_food_facts


def search_local(db: Session, query: str, limit: int = 30) -> list[Food]:
    stmt = (
        select(Food)
        .where(or_(Food.name.ilike(f"%{query}%"), Food.brand.ilike(f"%{query}%")))
        .order_by((Food.source == FoodSource.TACO).desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def search_with_open_food_facts_fallback(db: Session, query: str, limit: int = 30) -> list[Food]:
    """Busca local primeiro (TACO + produtos já cacheados). Se vier pouco
    resultado, complementa com uma busca ao vivo no Open Food Facts, cacheando
    o que voltar novo — próximas buscas iguais já saem 100% do banco local."""
    local_results = search_local(db, query, limit)
    if len(local_results) >= limit:
        return local_results

    try:
        remote_products = open_food_facts.search_by_name(query, page_size=limit)
    except Exception:
        return local_results

    known_external_ids = {f.external_id for f in local_results if f.external_id}
    cached: list[Food] = []
    for product in remote_products:
        if not product["external_id"] or product["external_id"] in known_external_ids:
            continue
        cached.append(_upsert_open_food_facts_product(db, product))

    db.commit()
    return local_results + cached


def get_by_barcode(db: Session, barcode: str) -> Food | None:
    cached = db.execute(select(Food).where(Food.barcode == barcode)).scalar_one_or_none()
    if cached is not None:
        return cached

    product = open_food_facts.fetch_by_barcode(barcode)
    if product is None:
        return None

    food = _upsert_open_food_facts_product(db, product)
    db.commit()
    return food


def _upsert_open_food_facts_product(db: Session, product: dict) -> Food:
    existing = db.execute(
        select(Food).where(
            Food.source == FoodSource.OPEN_FOOD_FACTS, Food.external_id == product["external_id"]
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    food = Food(source=FoodSource.OPEN_FOOD_FACTS, **product)
    db.add(food)
    db.flush()
    return food
