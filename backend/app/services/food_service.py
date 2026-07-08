from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.text import normalize_search_text
from app.models.food import Food, FoodSource
from app.services import open_food_facts


def search_local(db: Session, query: str, limit: int = 30) -> list[Food]:
    """Busca no banco local (TACO + produtos OFF já cacheados). Casa sem acento
    e sem maiúsculas via a coluna search_text ("pao" acha "Pão"). Cada palavra
    da busca precisa aparecer (AND), então "pao integral" filtra os dois."""
    norm = normalize_search_text(query)
    terms = [t for t in norm.split() if t]
    stmt = select(Food)
    for term in terms:
        stmt = stmt.where(Food.search_text.like(f"%{term}%"))
    # TACO (alimentos genéricos, base brasileira) primeiro, depois marcas.
    stmt = stmt.order_by((Food.source == FoodSource.TACO).desc(), Food.name).limit(limit)
    return list(db.execute(stmt).scalars())


def search_brands_live(db: Session, query: str, limit: int = 30) -> list[Food]:
    """Consulta o Open Food Facts ao vivo e cacheia os produtos novos — traz
    marcas (brasileiras e de outros países) que ainda não estão no banco.
    Chamada em separado da busca local pra não travar a digitação: o app
    mostra o local na hora e encaixa as marcas quando isto retorna."""
    try:
        remote_products = open_food_facts.search_by_name(query, page_size=limit)
    except Exception:
        return []

    # Evita duplicar o que já está local (mesmo código de barras/external_id).
    existing_ids = {
        f.external_id
        for f in db.execute(
            select(Food).where(Food.source == FoodSource.OPEN_FOOD_FACTS)
        ).scalars()
        if f.external_id
    }
    out: list[Food] = []
    seen: set[str] = set()
    for product in remote_products:
        ext = product.get("external_id")
        if not ext or ext in seen:
            continue
        seen.add(ext)
        if ext in existing_ids:
            existing = db.execute(
                select(Food).where(
                    Food.source == FoodSource.OPEN_FOOD_FACTS, Food.external_id == ext
                )
            ).scalar_one_or_none()
            if existing is not None:
                out.append(existing)
            continue
        out.append(_upsert_open_food_facts_product(db, product))
    db.commit()
    return out


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
