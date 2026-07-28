"""Cliente da API do FatSecret Platform — busca de alimentos de marca.

OAuth2 client-credentials: client_id/secret vêm SÓ de variável de ambiente
(app.core.config.Settings) — nunca hardcoded no código. Sem as duas
configuradas, `search_by_name` devolve lista vazia e o app continua
funcionando normalmente só com TACO + Open Food Facts.

Prioridade pro Brasil: o parâmetro `region=BR` (+ `language=pt`) do próprio
FatSecret dá precedência ao catálogo local — marcas e produtos vendidos no
Brasil aparecem na frente dos internacionais. Não precisa reordenar na mão.
"""

from __future__ import annotations

import base64
import re
import threading
import time

import requests

from app.core.config import settings

TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
SEARCH_URL = "https://platform.fatsecret.com/rest/server.api"
TIMEOUT_SECONDS = 8

_token_lock = threading.Lock()
_token: str | None = None
_token_expires_at = 0.0

_cache_lock = threading.Lock()
_CACHE_TTL_S = 600.0
_search_cache: dict[str, tuple[float, list[dict]]] = {}


def _configured() -> bool:
    return bool(settings.fatsecret_client_id and settings.fatsecret_client_secret)


def _get_token() -> str | None:
    """Token OAuth2 client-credentials, cacheado até perto de expirar."""
    global _token, _token_expires_at
    if not _configured():
        return None
    with _token_lock:
        if _token and time.monotonic() < _token_expires_at:
            return _token
        creds = f"{settings.fatsecret_client_id}:{settings.fatsecret_client_secret}".encode()
        auth = base64.b64encode(creds).decode()
        response = requests.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials", "scope": "basic"},
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        _token = payload["access_token"]
        ttl = int(payload.get("expires_in", 3600))
        # Renova um pouco antes do vencimento real, pra nunca usar um token
        # expirado bem no limite de uma corrida entre requisições.
        _token_expires_at = time.monotonic() + max(ttl - 60, 60)
        return _token


# `food_description` do foods.search vem como texto livre, ex.:
# "Per 100g - Calories: 52kcal | Fat: 0.17g | Carbs: 13.81g | Protein: 0.26g"
_DESC_RE = re.compile(
    r"per\s+100\s*g\s*-\s*calories:\s*([\d.]+)\s*kcal\s*\|\s*fat:\s*([\d.]+)\s*g\s*\|\s*carbs:\s*([\d.]+)\s*g\s*\|\s*protein:\s*([\d.]+)\s*g",
    re.IGNORECASE,
)


def _parse_description(desc: str) -> dict | None:
    """Só aceita quando a descrição é POR 100g. Porções diferentes ("Per 1
    fatia", "Per 1 copo") não dão pra normalizar sem o peso da porção — o
    foods.search não devolve isso (só o foods.get faria, com o custo de mais
    uma chamada por item). Descartar é mais seguro que mostrar número errado."""
    m = _DESC_RE.search(desc or "")
    if not m:
        return None
    kcal, fat, carbs, prot = (float(x) for x in m.groups())
    if kcal <= 0 or kcal > 900:  # mesmo teto físico do open_food_facts.py
        return None
    return {
        "kcal_per_100g": kcal,
        "fat_g_per_100g": fat,
        "carbs_g_per_100g": carbs,
        "protein_g_per_100g": prot,
    }


def _normalize(food: dict) -> dict | None:
    macros = _parse_description(food.get("food_description", ""))
    if macros is None:
        return None
    food_id = food.get("food_id")
    if not food_id:
        return None
    return {
        "external_id": str(food_id),
        "barcode": None,
        "name": food.get("food_name") or "Produto sem nome",
        "brand": food.get("brand_name") or None,
        **macros,
        "fiber_g_per_100g": None,
        "sodium_mg_per_100g": None,
        "sugar_g_per_100g": None,
        "default_portion_g": 100.0,
        "default_portion_label": None,
    }


def search_by_name(
    query: str, page_size: int = 25, region: str = "BR", language: str = "pt"
) -> list[dict]:
    """Alimentos de marca no FatSecret, priorizando o catálogo do Brasil.
    Cache por termo, igual ao open_food_facts.py. Vazio se não configurado,
    sem token, ou se a API falhar — nunca derruba a busca do app."""
    if not _configured():
        return []

    chave = f"{query.strip().lower()}|{page_size}|{region}|{language}"
    agora = time.monotonic()
    with _cache_lock:
        achado = _search_cache.get(chave)
        if achado and agora - achado[0] < _CACHE_TTL_S:
            return achado[1]

    try:
        token = _get_token()
        if token is None:
            return []
        response = requests.get(
            SEARCH_URL,
            params={
                "method": "foods.search",
                "search_expression": query,
                "format": "json",
                "max_results": page_size,
                "region": region,
                "language": language,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, KeyError):
        return []

    foods = (payload.get("foods") or {}).get("food") or []
    if isinstance(foods, dict):  # 1 resultado só: a API devolve objeto, não lista
        foods = [foods]

    resultado = [n for n in (_normalize(f) for f in foods) if n is not None]
    if resultado:
        with _cache_lock:
            _search_cache[chave] = (agora, resultado)
    return resultado
