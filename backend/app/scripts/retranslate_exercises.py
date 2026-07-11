"""Re-traduz os nomes dos exercícios JÁ no banco usando o tradutor
composicional novo (app/data/exercise_translator.py), sem re-seedar.

Casa cada exercício importado (video_url do free-exercise-db) com o nome em
INGLÊS do JSON original via o slug da pasta na URL
(.../exercises/<slug>/0.jpg -> id "<slug>" no JSON). Só toca nos importados;
não mexe nos exercícios curados (video_url nulo, que já têm nomes bons).

Uso: python -m app.scripts.retranslate_exercises
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.data.exercise_translator import translate_exercise_name
from app.models.exercise import Exercise

IMAGE_BASE = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/"
JSON_PATH = Path(__file__).resolve().parents[1] / "data" / "exercises_open.json"


def _slug_from_url(url: str) -> str | None:
    # .../exercises/<slug>/0.jpg
    if "/exercises/" not in url:
        return None
    tail = url.split("/exercises/", 1)[1]
    return tail.split("/", 1)[0] if "/" in tail else None


def run() -> None:
    en_by_slug = {row["id"]: row["name"] for row in json.loads(JSON_PATH.read_text(encoding="utf-8"))}
    db = SessionLocal()
    try:
        rows = list(
            db.execute(select(Exercise).where(Exercise.video_url.like(f"{IMAGE_BASE}%"))).scalars()
        )
        taken = {
            n.lower()
            for (n,) in db.execute(
                select(Exercise.name).where(~Exercise.video_url.like(f"{IMAGE_BASE}%"))
            )
        }
        changed = 0
        for ex in rows:
            slug = _slug_from_url(ex.video_url or "")
            english = en_by_slug.get(slug)
            if not english:
                continue
            new_name = translate_exercise_name(english)
            # não colide com os curados nem entre si
            base = new_name
            n = 2
            while new_name.lower() in taken:
                new_name = f"{base} (variação {n})"
                n += 1
            taken.add(new_name.lower())
            if new_name != ex.name:
                ex.name = new_name
                changed += 1
        db.commit()
        print(f"Re-traduzidos: {changed} de {len(rows)} exercícios importados.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
