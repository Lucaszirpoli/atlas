import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.text import normalize_search_text
from app.models.food import Food, FoodSource
from app.services import open_food_facts


def _stem(term: str) -> str:
    """Reduz plurais ao singular pra a busca casar os dois. Trata o plural
    simples ("ovos"->"ovo", "bananas"->"banana") e os plurais em -ão do
    português ("pães"->"pão"->"pao", "aviões"->"aviao"). Sem acento (o texto
    já vem normalizado)."""
    if len(term) >= 4 and (term.endswith("oes") or term.endswith("aes")):
        return term[:-3] + "ao"  # paes->pao, avioes->aviao
    return term[:-1] if len(term) >= 4 and term.endswith("s") else term


def search_local(db: Session, query: str, limit: int = 30) -> list[Food]:
    """Busca no banco local (TACO + produtos OFF já cacheados). Casa sem acento
    e sem maiúsculas via a coluna search_text ("pao" acha "Pão"), tolera plural
    e RE-ORDENA por relevância: nome que começa com o termo e nomes curtos
    primeiro (então "banana" traz "Banana", não "Açaí com granola e banana")."""
    norm = normalize_search_text(query)
    terms = [t for t in norm.split() if t]
    if not terms:
        return []
    stems = [_stem(t) for t in terms]

    stmt = select(Food)
    for stem in stems:
        stmt = stmt.where(Food.search_text.like(f"%{stem}%"))
    # Puxa um conjunto maior (TACO e nomes curtos primeiro) e reordena em Python.
    stmt = stmt.order_by((Food.source == FoodSource.TACO).desc(), func.length(Food.search_text)).limit(
        max(limit * 5, 40)
    )
    candidates = list(db.execute(stmt).scalars())

    def score(f: Food) -> float:
        st = f.search_text or ""
        s = 0.0
        # começa exatamente com o primeiro termo (ex: "banana ...") — forte sinal
        if stems and re.match(rf"\b{re.escape(stems[0])}", st):
            s += 200
        # cada termo como início de palavra (casa singular/plural: \bovo pega "ovos")
        for stem in stems:
            if re.search(rf"\b{re.escape(stem)}", st):
                s += 60
        if norm and st == norm:
            s += 400  # nome idêntico à busca
        if f.source == FoodSource.TACO:
            s += 30
        # Preparo comum de um alimento base (o que a pessoa mais registra:
        # "arroz cozido", "frango grelhado") ganha um empurrão à frente do prato
        # composto ("arroz carreteiro") que só era curto.
        if re.search(r"\b(cozid|grelhad|assad|cru|frit)", st):
            s += 25
        s -= len(st) * 0.4  # nomes mais curtos primeiro
        return s

    candidates.sort(key=score, reverse=True)

    # Dedup por nome exibido: TACO + curado às vezes têm o MESMO nome com kcal
    # levemente diferente ("Arroz carreteiro" 2×). Mantém o de maior score.
    vistos: set[str] = set()
    unicos: list[Food] = []
    for f in candidates:
        chave = (f.name or "").strip().lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(f)
    return unicos[:limit]


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
