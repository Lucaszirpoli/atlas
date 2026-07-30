"""Cliente da API pública do Open Food Facts.
Gratuita, sem chave — só exige um User-Agent identificando a aplicação.
"""

import re
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
# Busca de marca: 6s por endpoint (o app encaixa as marcas de forma assíncrona,
# mas 8s×vários é lento demais se todos flaparem).
_SEARCH_TIMEOUT_S = 6
# O OFF é instável (503/502 intermitente) e os serviços de busca caem de forma
# INDEPENDENTE — num dado momento a search-a-licious pode estar 502 e a cgi de
# pé, ou o contrário (visto ao vivo: search-a-licious 502 enquanto o product API
# respondia 200). Tentar UM só endpoint era o que fazia "não aparecer marca
# brasileira". Aqui a gente cai em cascata pelos três até um responder.
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


# Palavras que aparecem depois de um "-" no nome e NÃO são marca — são preparo,
# sabor ou qualificação do produto. Sem esta lista, "Arroz - integral" viraria
# marca "integral".
_NAO_E_MARCA = {
    "integral", "light", "diet", "zero", "tradicional", "cremoso", "cremosa",
    "cru", "crua", "cozido", "cozida", "assado", "assada", "frito", "frita",
    "desnatado", "semidesnatado", "em po", "em pó", "sem gluten", "sem glúten",
    "sem lactose", "sem acucar", "sem açúcar", "com sal", "sem sal",
    "organico", "orgânico", "congelado", "congelada", "defumado", "defumada",
    "sabor", "unidade", "pacote", "kg", "g", "ml", "l",
}


def _marca_no_nome(nome: str, marca_atual: str | None) -> tuple[str, str | None]:
    """Extrai a marca de dentro do NOME quando o OFF deixou o campo `brands`
    vazio — padrão "Cuzcuz - Gostozin", "Creme de ricota light ervas finas -
    Godam". Devolve (nome_limpo, marca).

    Por que importa: sem isto, esses produtos entram como alimentos SEM MARCA e
    poluem a busca com vários homônimos de calorias diferentes (o usuário
    encontrou 4 "Cuzcuz" variando de 112 a 354 kcal/100g, todos sem marca
    aparente, sem jeito de saber qual era qual). Com a marca no lugar certo eles
    viram produtos legítimos e distinguíveis — que é a regra do produto: pode ter
    vários homônimos, desde que cada um mostre a marca.
    """
    if marca_atual:
        return nome, marca_atual
    if " - " not in nome:
        return nome, None
    cabeca, _, cauda = nome.rpartition(" - ")
    cauda = cauda.strip()
    cabeca = cabeca.strip()
    # Cauda tem que parecer nome de marca: curta, não vazia, e não uma palavra
    # de preparo/sabor. Cabeça tem que sobrar algo que sirva de nome.
    if not cauda or not cabeca or len(cauda.split()) > 4:
        return nome, None
    if cauda.lower() in _NAO_E_MARCA or any(p == cauda.lower() for p in _NAO_E_MARCA):
        return nome, None
    return cabeca, cauda


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

    # `brands` vem como STRING no endpoint de código de barras e como LISTA no de
    # busca (search-a-licious). Sem normalizar, a marca chegaria no app como
    # "['Aurora']". Quando vem vazia, tenta achar a marca dentro do nome.
    nome = product.get("product_name") or product.get("product_name_pt") or "Produto sem nome"
    nome, marca = _marca_no_nome(nome.strip(), _marca(product.get("brands")))

    return {
        "external_id": product.get("code") or product.get("_id"),
        "barcode": product.get("code"),
        "name": nome,
        "brand": marca,
        "kcal_per_100g": kcal,
        "protein_g_per_100g": prot,
        "carbs_g_per_100g": carb,
        "fat_g_per_100g": gord,
        "fiber_g_per_100g": nutriments.get("fiber_100g"),
        "sodium_mg_per_100g": sodium_g * 1000 if sodium_g is not None else None,
        "sugar_g_per_100g": nutriments.get("sugars_100g"),
        # A porção do fabricante, quando ele informa. Produto de marca quase
        # nunca se come em 100 g: uma barrinha tem 25 g, um pote de iogurte
        # 90 g, um scoop de whey 30 g. Sem isto o app abria TUDO em 100 g e a
        # pessoa tinha que corrigir na mão em todo registro.
        "default_portion_g": _porcao_em_gramas(product) or 100.0,
        "default_portion_label": product.get("serving_size"),
    }


# "25 g", "1 barrinha (25g)", "30g (1 scoop)", "250 ml".
_GRAMAS_NA_PORCAO = re.compile(r"(\d+(?:[.,]\d+)?)\s*(g|gm|gr|ml)\b", re.IGNORECASE)


def _porcao_em_gramas(product: dict) -> float | None:
    """Peso de UMA porção do produto, na ordem em que o OFF é confiável:

    1. `serving_quantity` — o campo numérico, já normalizado pelo OFF;
    2. o número escrito em `serving_size` ("1 barrinha (25 g)" -> 25);
    3. `product_quantity` quando o pacote inteiro é uma porção só (até 60 g/ml:
       barrinha, sachê, iogurte). Acima disso é embalagem pra várias porções e
       usar o peso do pacote seria pior que os 100 g.

    ml conta como g: pra bebida a densidade é ~1 e o erro é menor que abrir
    um suco de caixinha em "100 g"."""
    bruto = product.get("serving_quantity")
    try:
        if bruto is not None and 0 < float(bruto) <= 5000:
            return float(bruto)
    except (TypeError, ValueError):
        pass

    achado = _GRAMAS_NA_PORCAO.search(str(product.get("serving_size") or ""))
    if achado:
        try:
            gramas = float(achado.group(1).replace(",", "."))
            if 0 < gramas <= 5000:
                return gramas
        except ValueError:
            pass

    try:
        pacote = float(product.get("product_quantity") or 0)
        if 0 < pacote <= 60:
            return pacote
    except (TypeError, ValueError):
        pass
    return None


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


def _buscar_search_a_licious(query: str, page_size: int) -> list[dict]:
    """Busca textual nova do OFF (search.openfoodfacts.org). Devolve `hits`,
    `brands` como LISTA. Filtro de país na própria query."""
    r = requests.get(
        SEARCH_URL,
        params={
            "q": f'{query} countries_tags:"en:brazil"',
            "page_size": page_size,
            "fields": "code,product_name,brands,nutriments,serving_size,serving_quantity,product_quantity",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=_SEARCH_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("hits", [])


def _buscar_cgi(base: str, query: str, page_size: int, so_brasil: bool) -> list[dict]:
    """Busca legada `cgi/search.pl`. Devolve `products`, `brands` como STRING.
    Existe em br.* e world.* — quando a search-a-licious está fora, uma destas
    costuma responder."""
    params = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": page_size,
        "fields": "code,product_name,brands,nutriments,serving_size,serving_quantity,product_quantity",
    }
    if so_brasil:
        params.update({"tagtype_0": "countries", "tag_contains_0": "contains", "tag_0": "brazil"})
    r = requests.get(
        f"{base}/cgi/search.pl", params=params, headers={"User-Agent": USER_AGENT}, timeout=_SEARCH_TIMEOUT_S
    )
    r.raise_for_status()
    return r.json().get("products", [])


def search_by_name(query: str, page_size: int = 25) -> list[dict]:
    """Produtos de marca vendidos no BRASIL que casem com o termo.

    Cai em CASCATA por três serviços de busca do OFF porque eles caem de forma
    independente (502/503 intermitente): a search-a-licious nova, a cgi do mundo
    filtrando Brasil e a cgi do subdomínio br. O primeiro que responder vence.
    Cache por termo (a busca dispara a cada tecla). Vazio só se TODOS caírem.
    """
    chave = f"{query.strip().lower()}|{page_size}"
    agora = time.monotonic()
    with _cache_lock:
        achado = _cache.get(chave)
        if achado and agora - achado[0] < _CACHE_TTL_S:
            return achado[1]

    estrategias = (
        lambda: _buscar_search_a_licious(query, page_size),
        lambda: _buscar_cgi("https://world.openfoodfacts.org", query, page_size, so_brasil=True),
        lambda: _buscar_cgi("https://br.openfoodfacts.org", query, page_size, so_brasil=False),
    )
    produtos: list[dict] = []
    for estrategia in estrategias:
        try:
            produtos = estrategia()
            if produtos:
                break
        except (requests.RequestException, ValueError):
            # ValueError cobre o HTML de erro com status 200. Tenta o próximo.
            continue

    normalizados = [_normalize_product(p) for p in produtos]
    resultado = [p for p in normalizados if p is not None]
    # Só cacheia sucesso: se todos caíram agora, não queremos travar "vazio" por
    # 10min — a próxima tecla tenta de novo e um serviço pode ter voltado.
    if resultado:
        with _cache_lock:
            _cache[chave] = (agora, resultado)
    return resultado
