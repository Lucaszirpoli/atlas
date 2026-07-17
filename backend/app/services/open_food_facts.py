"""Cliente da API pública do Open Food Facts.
Gratuita, sem chave — só exige um User-Agent identificando a aplicação.
"""

import threading
import time

import requests

USER_AGENT = "appfit/0.1 (contato: lucaszirpoli@gmail.com)"
# Leitura de produto por código de barras: o subdomínio br responde bem.
BASE_URL = "https://br.openfoodfacts.org"
# BUSCA por nome: search-a-licious, a busca textual nova do OFF.
#
# Foram três endpoints até achar o certo:
# 1. `br.openfoodfacts.org/cgi/search.pl` (o que estava em uso): legado e
#    instável — devolveu 503 em 2 de 3 tentativas. O app engolia a falha calado
#    ("se as marcas falharem, o local já está na tela"), então o usuário via
#    "quase nenhuma marca brasileira" quando na verdade a busca é que morria.
# 2. `world.openfoodfacts.org/api/v2/search`: responde, mas **ignora
#    search_terms** — é API de FILTROS, não de texto. "iogurte", "biscoito" e
#    "requeijão" devolviam os MESMOS 22 produtos. Trocaria uma busca quebrada
#    por uma que não busca.
# 3. search-a-licious: busca textual de verdade, aceita filtro de país na
#    própria query e devolve nutriments. É esta.
SEARCH_URL = "https://search.openfoodfacts.org/search"
TIMEOUT_SECONDS = 8
# O OFF é instável (503 intermitente, mesmo com pouco tráfego). Sem retentativa,
# a busca de marca é uma moeda ao ar.
_TENTATIVAS = 3
_ESPERA_INICIAL_S = 0.6

# Cache em memória por termo. Além de aliviar o OFF, faz a segunda digitação da
# mesma palavra responder na hora — a busca acontece a cada tecla.
_CACHE_TTL_S = 600.0
_cache: dict[str, tuple[float, list[dict]]] = {}
_cache_lock = threading.Lock()


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


def _marca(valor) -> str | None:
    """Normaliza o campo de marca — os dois endpoints do OFF divergem no tipo."""
    if isinstance(valor, list):
        return ", ".join(str(v) for v in valor if v) or None
    return valor or None


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
        # `brands` vem como STRING no endpoint de código de barras e como LISTA
        # no de busca (search-a-licious). Sem normalizar, a marca chegaria no
        # app como "['Aurora']".
        "brand": _marca(product.get("brands")),
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


def search_by_name(query: str, page_size: int = 25) -> list[dict]:
    """Produtos de marca vendidos no BRASIL que casem com o termo.

    Com cache e retentativa porque o OFF cai muito (503 intermitente): sem
    isso, a maioria das buscas voltava vazia e o app parecia não ter marca
    brasileira nenhuma.
    """
    chave = f"{query.strip().lower()}|{page_size}"
    agora = time.monotonic()
    with _cache_lock:
        achado = _cache.get(chave)
        if achado and agora - achado[0] < _CACHE_TTL_S:
            return achado[1]

    produtos: list[dict] = []
    espera = _ESPERA_INICIAL_S
    for tentativa in range(_TENTATIVAS):
        try:
            response = requests.get(
                SEARCH_URL,
                params={
                    # O filtro de país vai na própria query. Sem ele vêm
                    # produtos do mundo todo e a marca brasileira some no meio.
                    "q": f'{query} countries_tags:"en:brazil"',
                    "page_size": page_size,
                    # `brands` só volta se pedido explicitamente.
                    "fields": "code,product_name,brands,nutriments,serving_size",
                },
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT_SECONDS,
            )
            if response.status_code == 503 and tentativa < _TENTATIVAS - 1:
                time.sleep(espera)
                espera *= 2
                continue
            response.raise_for_status()
            produtos = response.json().get("hits", [])
            break
        except (requests.RequestException, ValueError):
            # ValueError cobre o JSON inválido que vem quando o OFF devolve
            # uma página de erro em HTML com status 200.
            if tentativa == _TENTATIVAS - 1:
                return []
            time.sleep(espera)
            espera *= 2

    normalizados = [_normalize_product(p) for p in produtos]
    resultado = [p for p in normalizados if p is not None]
    with _cache_lock:
        _cache[chave] = (agora, resultado)
    return resultado
