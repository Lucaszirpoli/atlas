import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.text import normalize_search_text
from app.models.food import Food, FoodSource
from app.services import fatsecret, open_food_facts


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

    # `hidden` = gêmeo perdedor de um alimento repetido. Fica fora da busca mas
    # continua existindo, porque o histórico de refeições aponta pra ele.
    stmt = select(Food).where(Food.hidden.is_(False))
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
        # composto ("arroz carreteiro") que só era curto. "Cru" fica de fora
        # deste empurrão de propósito: quem registra o que comeu quase sempre
        # comeu preparado, não o ingrediente cru — dar o mesmo peso fazia
        # "arroz, tipo 1, cru" competir de igual pra igual com "arroz cozido"
        # numa busca por "arroz". Cru continua achável (o termo bate igual),
        # só não fura na frente do que as pessoas realmente comem.
        if re.search(r"\b(cozid|grelhad|assad|frit)", st):
            s += 25
        s -= len(st) * 0.4  # nomes mais curtos primeiro
        return s

    candidates.sort(key=score, reverse=True)

    # Dedup por nome exibido + MARCA. TACO e curado às vezes têm o mesmo nome com
    # kcal levemente diferente ("Arroz carreteiro" 2×) e aí só um deve ficar.
    #
    # A marca entra na chave porque produtos de marcas DIFERENTES com o mesmo nome
    # são resultados diferentes e legítimos — é a regra do produto: "pode ter
    # pipoca A, pipoca B e pipoca C, desde que cada uma mostre a marca". Sem ela,
    # "Cuzcuz" da Gostozin e "Cuzcuz" da Rainha do Campo se eliminavam e a pessoa
    # só via um dos dois, sem saber que o outro existia. Quem some agora é só o
    # homônimo SEM marca, que é o que o dedup_foods já esconde na origem.
    vistos: set[tuple[str, str]] = set()
    unicos: list[Food] = []
    for f in candidates:
        chave = ((f.name or "").strip().lower(), (f.brand or "").strip().lower())
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

    # Nomes que a busca LOCAL já entrega. Um produto do OFF sem marca que repete
    # um nome do TACO é ruído puro: mesma comida, dado pior, e a pessoa fica com
    # duas linhas iguais de calorias diferentes sem jeito de escolher.
    nomes_locais = {
        normalize_search_text(f.name or "")
        for f in db.execute(select(Food).where(Food.hidden.is_(False))).scalars()
    }

    out: list[Food] = []
    seen: set[str] = set()
    nomes_desta_busca: set[str] = set()
    for product in remote_products:
        ext = product.get("external_id")
        if not ext or ext in seen:
            continue
        seen.add(ext)
        # ESTA É A BUSCA DE MARCAS. Produto sem marca aqui não é o que a pessoa
        # pediu, e era a origem da poluição do banco: cada busca GRAVAVA os
        # genéricos do OFF como alimento permanente — foi assim que apareceram 4
        # "Cuzcuz" de 112 a 354 kcal/100g, todos sem marca aparente e sem jeito
        # de saber qual era cru e qual era cozido. Sem marca não entra na lista
        # e, o mais importante, não é gravado.
        #
        # O código de barras continua achando esses produtos: get_by_barcode não
        # passa por aqui e não filtra marca. Quem escaneia está com o produto na
        # mão; quem digita "cuscuz" quer uma resposta em que dê pra escolher.
        if not (product.get("brand") or "").strip():
            continue
        nome_norm = normalize_search_text(product.get("name") or "")
        if nome_norm and (nome_norm in nomes_locais or nome_norm in nomes_desta_busca):
            continue
        if nome_norm:
            nomes_desta_busca.add(nome_norm)
        if ext in existing_ids:
            existing = db.execute(
                select(Food).where(
                    Food.source == FoodSource.OPEN_FOOD_FACTS, Food.external_id == ext
                )
            ).scalar_one_or_none()
            # `hidden` = gêmeo perdedor de um produto repetido. A busca local já
            # filtra; sem filtrar aqui também, ele voltava pela porta dos fundos
            # (eram os dois "Cuzcuz" de 125 e 340 kcal na mesma lista).
            if existing is not None and not existing.hidden:
                out.append(existing)
            continue
        out.append(_upsert_open_food_facts_product(db, product))
    db.commit()
    return out


def search_fatsecret_live(db: Session, query: str, limit: int = 30) -> list[Food]:
    """Consulta o FatSecret ao vivo e cacheia os produtos novos — marcas com
    prioridade pro catálogo do Brasil (region=BR, ver services/fatsecret.py).
    Mesmo padrão do Open Food Facts: busca em separado, o app encaixa quando
    isto retorna. Sem credenciais configuradas, devolve vazio sem erro."""
    try:
        remote_products = fatsecret.search_by_name(query, page_size=limit)
    except Exception:
        return []

    existing_ids = {
        f.external_id
        for f in db.execute(select(Food).where(Food.source == FoodSource.FATSECRET)).scalars()
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
                select(Food).where(Food.source == FoodSource.FATSECRET, Food.external_id == ext)
            ).scalar_one_or_none()
            # `hidden` = gêmeo perdedor de um produto repetido. A busca local já
            # filtra; sem filtrar aqui também, ele voltava pela porta dos fundos
            # (eram os dois "Cuzcuz" de 125 e 340 kcal na mesma lista).
            if existing is not None and not existing.hidden:
                out.append(existing)
            continue
        out.append(_upsert_product(db, FoodSource.FATSECRET, product))
    db.commit()
    return out


def get_by_barcode(db: Session, barcode: str) -> Food | None:
    cached = db.execute(select(Food).where(Food.barcode == barcode)).scalar_one_or_none()
    if cached is not None:
        return cached

    product = open_food_facts.fetch_by_barcode(barcode)
    if product is None:
        return None

    food = _upsert_product(db, FoodSource.OPEN_FOOD_FACTS, product)
    db.commit()
    return food


def _upsert_open_food_facts_product(db: Session, product: dict) -> Food:
    return _upsert_product(db, FoodSource.OPEN_FOOD_FACTS, product)


def _upsert_product(db: Session, source: FoodSource, product: dict) -> Food:
    existing = db.execute(
        select(Food).where(Food.source == source, Food.external_id == product["external_id"])
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    food = Food(source=source, **product)
    db.add(food)
    db.flush()
    return food
