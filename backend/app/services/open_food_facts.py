"""Cliente da API pública do Open Food Facts (br.openfoodfacts.org).
Gratuita, sem chave — só exige um User-Agent identificando a aplicação.
"""
import requests

USER_AGENT = "appfit/0.1 (contato: lucaszirpoli@gmail.com)"
BASE_URL = "https://br.openfoodfacts.org"
TIMEOUT_SECONDS = 8


def _normalize_product(product: dict) -> dict | None:
    nutriments = product.get("nutriments", {})
    kcal = nutriments.get("energy-kcal_100g")
    if kcal is None:
        return None

    sodium_g = nutriments.get("sodium_100g")

    return {
        "external_id": product.get("code") or product.get("_id"),
        "barcode": product.get("code"),
        "name": product.get("product_name") or product.get("product_name_pt") or "Produto sem nome",
        "brand": product.get("brands"),
        "kcal_per_100g": kcal,
        "protein_g_per_100g": nutriments.get("proteins_100g", 0) or 0,
        "carbs_g_per_100g": nutriments.get("carbohydrates_100g", 0) or 0,
        "fat_g_per_100g": nutriments.get("fat_100g", 0) or 0,
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
