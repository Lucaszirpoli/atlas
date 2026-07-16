"""Busca de academias no mapa + matemática de distância do check-in.

A busca usa o **Nominatim** (serviço oficial de busca do OpenStreetMap):
gratuito, sem chave de API, e cobre as academias do Brasil (verificado: Smart
Fit, Bio Ritmo, Selfit etc. retornam com endereço e coordenadas). É uma busca
por NOME limitada à região da pessoa — que é exatamente o fluxo do app ("pesquise
sua academia"). A API de listar-tudo-por-perto (Overpass) foi descartada: os
servidores públicos dela vivem instáveis (504/timeout nos testes).

Regras de uso do Nominatim que este módulo respeita (senão eles bloqueiam):
- User-Agent identificando o app.
- No máximo 1 requisição por segundo (throttle simples por processo).
"""

from __future__ import annotations

import json
import math
import threading
import time
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "AtlasFitnessApp/1.0 (contato@atlas.app)"
_MIN_INTERVAL_S = 1.1  # política do Nominatim: 1 req/s

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


def search_gyms(query: str, lat: float, lng: float, limit: int = 12) -> list[dict]:
    """Busca academias pelo nome perto da pessoa. Devolve [] se a busca falhar
    (rede/serviço fora) — a tela mostra o erro sem quebrar."""
    q = (query or "").strip()
    if not q:
        return []

    params = urllib.parse.urlencode(
        {
            "q": q,
            "format": "jsonv2",
            "limit": max(1, min(limit, 20)),
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
    out.sort(key=lambda g: g["distance_m"])
    return out
