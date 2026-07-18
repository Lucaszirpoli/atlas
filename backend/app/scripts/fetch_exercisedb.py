"""Baixa o catálogo COMPLETO da ExerciseDB pra dentro do repositório — UMA VEZ.

Gera dois artefatos versionados que o deploy usa OFFLINE (sem tocar na API):
  - app/data/exercisedb_catalog.json  : os 1394 exercícios (campos que usamos)
  - app/static/exercisedb/{id}.gif    : o GIF demonstrativo de cada um (~124 MB)

POR QUE separar isto do seed: o deploy do Railway roda o seed a cada subida, e
NÃO pode depender da API (cota, latência, rede) nem rebaixar a experiência se a
ExerciseDB cair. Baixar aqui, commitar, e o seed só lê arquivo local.

Idempotente e resumível: pula GIF que já existe em disco. Se a cota estourar no
meio, é só rodar de novo que ele continua de onde parou.

Uso:
  python -m app.scripts.fetch_exercisedb            # catálogo + todos os GIFs
  python -m app.scripts.fetch_exercisedb --json     # só o JSON (rápido)
  python -m app.scripts.fetch_exercisedb --limit 20 # amostra pra testar
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

from app.core.config import settings

API_HOST = "exercisedb.p.rapidapi.com"
DATA_PATH = Path(__file__).parent.parent / "data" / "exercisedb_catalog.json"
GIF_DIR = Path(__file__).parent.parent / "static" / "exercisedb"
GIF_RESOLUTION = 180  # ~91 KB por GIF; 360 quadruplica o tamanho do repo.

# Só os campos que o seed usa — corta instructions/description (longos) pra
# manter o JSON versionado enxuto.
_KEEP = ("id", "name", "bodyPart", "target", "secondaryMuscles", "equipment", "category", "difficulty")


def _get_with_retry(client: httpx.Client, url: str, params: dict, tentativas: int = 6):
    """GET com recuo exponencial no 429 (limite POR SEGUNDO, não cota mensal)."""
    espera = 1.0
    for i in range(tentativas):
        resp = client.get(url, params=params)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp
        if i < tentativas - 1:
            time.sleep(espera)
            espera = min(espera * 2, 16)
    resp.raise_for_status()
    return resp


def fetch_catalog(client: httpx.Client) -> list[dict]:
    resp = _get_with_retry(client, f"https://{API_HOST}/exercises", {"limit": 2000, "offset": 0})
    data = resp.json()
    trimmed = [{k: row.get(k) for k in _KEEP} for row in data]
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(trimmed, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Catálogo salvo: {len(trimmed)} exercícios -> {DATA_PATH}")
    return trimmed


def download_gifs(client: httpx.Client, catalog: list[dict], limit: int | None) -> None:
    GIF_DIR.mkdir(parents=True, exist_ok=True)
    alvos = catalog[:limit] if limit else catalog
    baixados = pulados = erros = 0
    for i, row in enumerate(alvos, 1):
        ex_id = row["id"]
        dest = GIF_DIR / f"{ex_id}.gif"
        if dest.exists() and dest.stat().st_size > 0:
            pulados += 1
            continue
        try:
            img = _get_with_retry(
                client,
                f"https://{API_HOST}/image",
                {"exerciseId": ex_id, "resolution": GIF_RESOLUTION},
            )
            dest.write_bytes(img.content)
            baixados += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  [erro] {ex_id} {row.get('name')}: {exc}")
            erros += 1
            continue
        if baixados % 50 == 0:
            rem = img.headers.get("x-ratelimit-requests-remaining")
            print(f"  {i}/{len(alvos)} — baixados {baixados}, cota restante {rem}")
        time.sleep(0.25)  # gentil com o rate limit por segundo
    print(f"\nGIFs: {baixados} baixados, {pulados} já existiam, {erros} erros. Dir: {GIF_DIR}")


def run(only_json: bool = False, limit: int | None = None) -> None:
    if not settings.rapidapi_exercisedb_key:
        print("RAPIDAPI_EXERCISEDB_KEY não configurada no .env — abortando.")
        return
    headers = {"x-rapidapi-host": API_HOST, "x-rapidapi-key": settings.rapidapi_exercisedb_key}
    with httpx.Client(headers=headers, timeout=60) as client:
        catalog = fetch_catalog(client)
        if only_json:
            return
        download_gifs(client, catalog, limit)


if __name__ == "__main__":
    args = sys.argv[1:]
    lim = None
    if "--limit" in args:
        lim = int(args[args.index("--limit") + 1])
    run(only_json="--json" in args, limit=lim)
