"""Cliente da API pública do Open Food Facts (br.openfoodfacts.org).
Gratuita, sem chave — só exige um User-Agent identificando a aplicação.
"""
import requests

USER_AGENT = "appfit/0.1 (contato: lucaszirpoli@gmail.com)"
BASE_URL = "https://br.openfoodfacts.org"
TIMEOUT_SECONDS = 8


# Limites físicos. Gordura pura tem 9 kcal/g, então 100g de QUALQUER coisa não
# passa de ~900 kcal — óleo, o alimento mais calórico que existe, dá 884.
_KCAL_MAX_POR_100G = 900.0
# Massa: 100g não podem conter mais de 100g de macronutriente.
_MACRO_MAX_POR_100G = 105.0  # 5g de folga pra arredondamento do rótulo


def _parece_confiavel(kcal: float, prot: float, carb: float, gord: float) -> bool:
    """Descarta produto do Open Food Facts com nutrição impossível.

    Os dados de lá são preenchidos pela comunidade e erram com frequência: o
    erro clássico é lançar as kcal da PORÇÃO no campo de 100g (um prato de
    500 kcal vira "500 kcal/100g"), ou lançar kJ como kcal (4,18x maior).
    Sem esta checagem o app mostrava "100g de ovo = 500 kcal" e o usuário,
    com razão, perde a confiança na contagem inteira.
    """
    if kcal <= 0 or kcal > _KCAL_MAX_POR_100G:
        return False
    if prot < 0 or carb < 0 or gord < 0:
        return False
    if prot + carb + gord > _MACRO_MAX_POR_100G:
        return False
    # Coerência com os macros (4/4/9), exigindo divergência grande em termos
    # RELATIVOS **e** ABSOLUTOS. As duas condições juntas são o que evita
    # barrar bebida alcoólica: álcool tem 7 kcal/g e não entra em P/C/G, então
    # cerveja (41 kcal, macros dão 15) e vinho (83, macros dão 11) divergem
    # muito em proporção, mas pouco em kcal — e são dados corretos. Já o erro
    # que interessa barrar é grande nas duas escalas (ovo com 500 kcal quando
    # os macros dão 146). Fibra e polióis entram na mesma folga.
    kcal_dos_macros = prot * 4 + carb * 4 + gord * 9
    if kcal_dos_macros > 10:
        divergencia = abs(kcal - kcal_dos_macros)
        muito_fora = kcal > kcal_dos_macros * 2.2 or kcal < kcal_dos_macros * 0.45
        if divergencia > 100 and muito_fora:
            return False
    return True


def _normalize_product(product: dict) -> dict | None:
    nutriments = product.get("nutriments", {})
    kcal = nutriments.get("energy-kcal_100g")
    if kcal is None:
        return None

    prot = nutriments.get("proteins_100g", 0) or 0
    carb = nutriments.get("carbohydrates_100g", 0) or 0
    gord = nutriments.get("fat_100g", 0) or 0
    try:
        if not _parece_confiavel(float(kcal), float(prot), float(carb), float(gord)):
            return None
    except (TypeError, ValueError):
        return None

    sodium_g = nutriments.get("sodium_100g")

    return {
        "external_id": product.get("code") or product.get("_id"),
        "barcode": product.get("code"),
        "name": product.get("product_name") or product.get("product_name_pt") or "Produto sem nome",
        "brand": product.get("brands"),
        "kcal_per_100g": kcal,
        "protein_g_per_100g": prot,
        "carbs_g_per_100g": carb,
        "fat_g_per_100g": gord,
        "fiber_g_per_100g": nutriments.get("fiber_100g"),
        "sodium_mg_per_100g": sodium_g * 1000 if sodium_g is not None else None,
        "sugar_g_per_100g": nutriments.get("sugars_100g"),
        "default_portion_g": 100.0,
        "default_portion_label": product.get("serving_size"),
    }


def fetch_by_barcode(barcode: str) -> dict | None:
    response = requests.get(
        f"{BASE_URL}/api/v2/product/{barcode}.json",
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != 1:
        return None
    return _normalize_product(payload["product"])


def search_by_name(query: str, page_size: int = 20) -> list[dict]:
    response = requests.get(
        f"{BASE_URL}/cgi/search.pl",
        params={
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": page_size,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    products = response.json().get("products", [])
    normalized = [_normalize_product(p) for p in products]
    return [p for p in normalized if p is not None]
