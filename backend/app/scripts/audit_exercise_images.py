"""Audita os GIFs já baixados: quais foram casados com o exercício ERRADO?

POR QUE: os 139 GIFs em app/static/exercise_images/ foram baixados com uma
regra de casamento frouxa (equipamento 0.4 + músculo 0.2 já passavam o corte de
0.45, então um candidato de NOME totalmente diferente era aceito). Resultado:
GIF de um movimento no exercício de outro.

Este script reconsulta a ExerciseDB e repontua com a regra corrigida
(backfill_exercise_images.score_candidate + NAME_FLOOR). Quem não passa é
listado como suspeito.

--apply remove o GIF suspeito e limpa a video_url: imagem errada é PIOR que
imagem nenhuma, porque ensina o movimento errado — e o exercício continua
buscável, só sem foto, até alguém achar a certa.

Uso:
  python -m app.scripts.audit_exercise_images           # só relata
  python -m app.scripts.audit_exercise_images --apply   # relata e remove
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.exercise import Exercise
from app.scripts.backfill_exercise_images import (
    API_HOST,
    MATCH_THRESHOLD,
    NAME_FLOOR,
    STATIC_DIR,
    guess_query,
    name_ratio,
    score_candidate,
)


def run(apply: bool = False) -> None:
    if not settings.rapidapi_exercisedb_key:
        print("RAPIDAPI_EXERCISEDB_KEY não configurada — abortando.")
        return

    db = SessionLocal()
    headers = {
        "X-RapidAPI-Key": settings.rapidapi_exercisedb_key,
        "X-RapidAPI-Host": API_HOST,
    }
    suspeitos: list[tuple[Exercise, str, float]] = []
    ok = sem_query = sem_candidato = 0

    try:
        # Só os que têm GIF LOCAL (os curados). Os importados vêm com a imagem
        # do próprio registro de origem — esses não têm risco de troca.
        alvos = [
            ex
            for ex in db.execute(select(Exercise).order_by(Exercise.id)).scalars()
            if (ex.video_url or "").startswith("/static/exercise_images/")
        ]
        print(f"Auditando {len(alvos)} exercícios com GIF local ...\n")

        with httpx.Client(timeout=20, headers=headers) as client:
            for ex in alvos:
                q = guess_query(ex.name)
                if not q:
                    sem_query += 1
                    continue
                try:
                    resp = client.get(
                        f"https://{API_HOST}/exercises/name/{q}",
                        params={"limit": 25},
                    )
                    resp.raise_for_status()
                    candidates = resp.json()
                except Exception as exc:  # noqa: BLE001
                    print(f"  [erro] {ex.name}: {exc}")
                    continue

                if not candidates:
                    sem_candidato += 1
                    continue

                best = max(candidates, key=lambda c: score_candidate(ex, c))
                nr = name_ratio(ex, best)
                if score_candidate(ex, best) < MATCH_THRESHOLD or nr < NAME_FLOOR:
                    suspeitos.append((ex, best.get("name", "?"), nr))
                else:
                    ok += 1
                time.sleep(0.15)  # educação com a API

        print(f"\n{'='*70}")
        print(f"OK (nome bate)      : {ok}")
        print(f"SEM padrão de busca : {sem_query}  (não dá pra auditar por aqui)")
        print(f"SEM candidato       : {sem_candidato}")
        print(f"SUSPEITOS           : {len(suspeitos)}")
        print(f"{'='*70}\n")
        for ex, cand, nr in suspeitos:
            print(f"  id={ex.id:<5} {ex.name[:38]:<38} melhor candidato: {cand[:30]:<30} nome={nr:.2f}")

        if apply and suspeitos:
            removidos = 0
            for ex, _, _ in suspeitos:
                gif = Path(STATIC_DIR) / f"{ex.id}.gif"
                if gif.exists():
                    gif.unlink()
                ex.video_url = None
                removidos += 1
            db.commit()
            print(f"\n{removidos} GIF(s) suspeito(s) removido(s). Exercício segue buscável, sem foto.")
        elif suspeitos:
            print("\n(rode com --apply pra remover os suspeitos)")
    finally:
        db.close()


if __name__ == "__main__":
    run(apply="--apply" in sys.argv)
