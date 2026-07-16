"""Busca de academias no mapa + matemática de distância do check-in.

Usa DUAS fontes do OpenStreetMap (ambas gratuitas, sem chave de API):

1. **Overpass** — lista TODAS as academias num raio ao redor da pessoa (por
   categoria: leisure=fitness_centre / amenity=gym). É o que faz aparecer a
   academia dela mesmo que ela digite o nome torto ou não digite nada.
2. **Nominatim** — busca por NOME. Pega redes/unidades que o Overpass às vezes
   não traz e garante o casamento quando a pessoa digita o nome certo.

Os resultados são unidos, deduplicados e ordenados: quem casa com o que foi
digitado vem primeiro, depois por distância.

Por que as duas: o Overpass público CAI com frequência (504/timeout — visto em
teste). Quando ele falha, a busca por nome segura sozinha, em vez de a tela
ficar vazia. Regras respeitadas: User-Agent identificando o app e 1 req/s no
Nominatim (throttle por processo).
"""

from __future__ import annotations

import difflib
import json
import math
import threading
import time
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
USER_AGENT = "AtlasFitnessApp/1.0 (contato@atlas.app)"
_MIN_INTERVAL_S = 1.1  # política do Nominatim: 1 req/s
NEARBY_RADIUS_M = 8000  # raio pra "academias da sua região"

_last_call_at = 0.0
_lock = threading.Lock()


def _throttle() -> None:
    global _last_call_at
    with _lock:
        wait = _MIN_INTERVAL_S - (time.monotonic() - _last_call_at)
        if wait > 0:
            time.sleep(wait)
        _last_call_at = time.monotonic()


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distância em metros entre dois pontos (fórmula de haversine)."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _viewbox(lat: float, lng: float, km: float = 12.0) -> str:
    """Caixa de busca ao redor da pessoa (limita a busca à região dela)."""
    dlat = km / 111.0
    dlng = km / (111.0 * max(math.cos(math.radians(lat)), 0.1))
    return f"{lng - dlng:.5f},{lat - dlat:.5f},{lng + dlng:.5f},{lat + dlat:.5f}"


def _nominatim_by_name(query: str, lat: float, lng: float, limit: int) -> list[dict]:
    """Academias que casam com o NOME digitado, dentro da região."""
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "limit": max(1, min(limit, 25)),
            "viewbox": _viewbox(lat, lng),
            "bounded": 1,
            "addressdetails": 1,
        }
    )
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}", headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        _throttle()
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read())
    except Exception:
        return []

    out: list[dict] = []
    for e in raw:
        try:
            elat, elng = float(e["lat"]), float(e["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        addr = e.get("address", {}) or {}
        rua = addr.get("road") or addr.get("pedestrian") or ""
        bairro = addr.get("suburb") or addr.get("neighbourhood") or addr.get("city_district") or ""
        cidade = addr.get("city") or addr.get("town") or addr.get("municipality") or ""
        endereco = ", ".join([p for p in (rua, bairro, cidade) if p]) or e.get("display_name", "")[:120]
        out.append(
            {
                "name": e.get("name") or endereco.split(",")[0] or "Academia",
                "address": endereco,
                "lat": elat,
                "lng": elng,
                "osm_id": f"{e.get('osm_type', '')}/{e.get('osm_id', '')}",
                "distance_m": round(haversine_m(lat, lng, elat, elng)),
            }
        )
    return out


# Cache das academias por região (chave = coords arredondadas ~1km). O Overpass
# público é intermitente: cacheando, uma vez que deu certo a lista continua
# aparecendo nas buscas seguintes em vez de sumir quando ele cai. Também evita
# martelar um serviço gratuito a cada tecla.
_NEARBY_TTL_S = 3600.0
_nearby_cache: dict[tuple[float, float], tuple[float, list[dict]]] = {}


def _overpass_nearby(lat: float, lng: float) -> list[dict]:
    """TODAS as academias mapeadas num raio ao redor da pessoa (por categoria).
    Devolve [] se o serviço estiver fora — a busca por nome cobre nesse caso."""
    cache_key = (round(lat, 2), round(lng, 2))
    hit = _nearby_cache.get(cache_key)
    if hit and (time.monotonic() - hit[0]) < _NEARBY_TTL_S:
        # recalcula a distância a partir da posição atual exata
        return [{**g, "distance_m": round(haversine_m(lat, lng, g["lat"], g["lng"]))} for g in hit[1]]

    r = NEARBY_RADIUS_M
    q = (
        f"[out:json][timeout:20];("
        f'node["leisure"="fitness_centre"](around:{r},{lat},{lng});'
        f'way["leisure"="fitness_centre"](around:{r},{lat},{lng});'
        f'node["amenity"="gym"](around:{r},{lat},{lng});'
        f");out center 60;"
    )
    data = urllib.parse.urlencode({"data": q}).encode()
    for url in OVERPASS_URLS:
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = json.loads(resp.read())
            break
        except Exception:
            continue
    else:
        return []

    out: list[dict] = []
    for e in raw.get("elements", []):
        tags = e.get("tags", {}) or {}
        name = tags.get("name")
        if not name:
            continue  # ponto sem nome não ajuda a pessoa a se reconhecer
        center = e if "lat" in e else e.get("center", {})
        try:
            elat, elng = float(center["lat"]), float(center["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        rua = tags.get("addr:street") or ""
        num = tags.get("addr:housenumber") or ""
        bairro = tags.get("addr:suburb") or tags.get("addr:neighbourhood") or ""
        cidade = tags.get("addr:city") or ""
        endereco = ", ".join([p for p in (f"{rua} {num}".strip(), bairro, cidade) if p])
        out.append(
            {
                "name": name,
                "address": endereco or None,
                "lat": elat,
                "lng": elng,
                "osm_id": f"{e.get('type', '')}/{e.get('id', '')}",
                "distance_m": round(haversine_m(lat, lng, elat, elng)),
            }
        )
    if out:
        _nearby_cache[cache_key] = (time.monotonic(), out)
    return out


def _name_score(query: str, name: str) -> float:
    """0..1 — o quanto o nome parece com o que a pessoa digitou."""
    q, n = query.lower().strip(), (name or "").lower()
    if not q:
        return 0.0
    if q in n:
        return 1.0
    return difflib.SequenceMatcher(None, q, n).ratio()


def search_gyms(query: str, lat: float, lng: float, limit: int = 25) -> list[dict]:
    """Academias da região da pessoa. Sem texto, lista as mais próximas; com
    texto, as parecidas com o nome vêm primeiro (mas as outras continuam na
    lista — a pessoa pode ter digitado torto ou não saber o nome exato)."""
    q = (query or "").strip()

    results = _overpass_nearby(lat, lng)
    if q:
        results += _nominatim_by_name(q, lat, lng, limit)

    # Dedup: mesmo osm_id, ou praticamente as mesmas coordenadas (~11m).
    seen: set = set()
    unique: list[dict] = []
    for g in results:
        key = g["osm_id"] if g.get("osm_id") and "/" in g["osm_id"] else None
        coord_key = (round(g["lat"], 4), round(g["lng"], 4))
        if key in seen or coord_key in seen:
            continue
        if key:
            seen.add(key)
        seen.add(coord_key)
        unique.append(g)

    if q:
        for g in unique:
            g["_score"] = _name_score(q, g["name"])
        # Casou bem com o nome primeiro; depois por distância.
        unique.sort(key=lambda g: (-round(g["_score"], 2), g["distance_m"]))
        for g in unique:
            g.pop("_score", None)
    else:
        unique.sort(key=lambda g: g["distance_m"])

    return unique[:limit]
