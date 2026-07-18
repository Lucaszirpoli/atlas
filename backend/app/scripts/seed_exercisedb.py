"""Popula a biblioteca de exercícios a partir do snapshot da ExerciseDB
(app/data/exercisedb_catalog.json + app/static/exercisedb/*.gif), e aposenta a
base antiga (free-exercise-db) escondendo-a — sem apagar, pra não quebrar as
rotinas e o histórico que referenciam o id por FK.

Roda no init_db a cada deploy. NÃO toca na API (lê só arquivo local). Idempotente:
casa por source_external_id, então reimportar ATUALIZA em vez de duplicar.

Uso: python -m app.scripts.seed_exercisedb
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import inspect, select, text

from app.core.db import SessionLocal, engine
from app.data.exercise_translator import translate_exercise_name
from app.data.exercisedb_map import (
    map_category,
    map_difficulty,
    map_equipment,
    map_muscle,
    map_secondary,
)
from app.models.exercise import Exercise

DATA_PATH = Path(__file__).parent.parent / "data" / "exercisedb_catalog.json"
GIF_DIR = Path(__file__).parent.parent / "static" / "exercisedb"


def ensure_columns() -> None:
    """ALTER TABLE idempotente (SQLite dev + Postgres prod). create_all não
    adiciona coluna em tabela já existente, então num banco antigo essas colunas
    faltariam e QUALQUER select(Exercise) do ORM estouraria 'no such column'.

    CRÍTICO: tem que rodar ANTES de qualquer select(Exercise) do init_db
    (backfill_exercise_category, retranslate_exercises, etc.), senão o boot
    inteiro morre e o backend não sobe (502). Por isso o init_db chama isto logo
    depois do create_all, e não só dentro de run()."""
    existentes = {c["name"] for c in inspect(engine).get_columns("exercises")}
    pg = engine.dialect.name == "postgresql"
    add_cols: list[tuple[str, str, str]] = [
        # (coluna, tipo postgres, tipo sqlite)
        ("name_en", "VARCHAR(150)", "VARCHAR(150)"),
        ("source_external_id", "VARCHAR(20)", "VARCHAR(20)"),
        ("is_hidden", "BOOLEAN NOT NULL DEFAULT FALSE", "BOOLEAN NOT NULL DEFAULT 0"),
    ]
    with engine.begin() as conn:
        for col, pg_type, sqlite_type in add_cols:
            if col in existentes:
                continue
            if pg:
                conn.execute(text(f"ALTER TABLE exercises ADD COLUMN IF NOT EXISTS {col} {pg_type}"))
            else:
                conn.execute(text(f"ALTER TABLE exercises ADD COLUMN {col} {sqlite_type}"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_exercises_source_external_id "
                 "ON exercises (source_external_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_exercises_name_en ON exercises (name_en)")
        )


def _gif_url(ex_id: str) -> str | None:
    """URL RELATIVA do GIF versionado, só se o arquivo existir de fato — nunca
    referencia imagem ausente (o app trataria como quebrada). O mobile prefixa
    o endereço do backend na hora de exibir."""
    return f"/static/exercisedb/{ex_id}.gif" if (GIF_DIR / f"{ex_id}.gif").exists() else None


def run() -> None:
    ensure_columns()

    if not DATA_PATH.exists():
        print(f"{DATA_PATH.name} ausente — rode fetch_exercisedb primeiro. Pulando.")
        return

    catalog = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        # Índice do que já foi importado (idempotência).
        existentes = {
            ex.source_external_id: ex
            for ex in db.execute(
                select(Exercise).where(Exercise.source_external_id.is_not(None))
            ).scalars()
        }

        inseridos = atualizados = 0
        for row in catalog:
            ex_id = row.get("id")
            en = (row.get("name") or "").strip()
            if not ex_id or not en:
                continue

            primary = map_muscle(row.get("target"), row.get("bodyPart"))
            campos = dict(
                name=translate_exercise_name(en)[:150],
                name_en=en[:150],
                primary_muscle_group=primary,
                secondary_muscle_groups=map_secondary(row.get("secondaryMuscles"), primary),
                equipment=map_equipment(row.get("equipment")),
                difficulty=map_difficulty(row.get("difficulty")),
                category=map_category(row.get("category")),
                video_url=_gif_url(ex_id),
                is_hidden=False,
                is_custom=False,
                source_external_id=ex_id,
            )

            ex = existentes.get(ex_id)
            if ex is None:
                db.add(Exercise(**campos))
                inseridos += 1
            else:
                for k, v in campos.items():
                    setattr(ex, k, v)
                atualizados += 1

        # Aposenta TUDO que não veio da ExerciseDB (free-exercise-db + curados
        # antigos): some da busca/picker/engine, mas continua no banco pra não
        # orfanar rotina/histórico. Só marca; nunca apaga.
        aposentados = (
            db.query(Exercise)
            .filter(Exercise.source_external_id.is_(None), Exercise.is_custom.is_(False))
            .update({Exercise.is_hidden: True}, synchronize_session=False)
        )

        db.commit()
        print(
            f"ExerciseDB: {inseridos} inseridos, {atualizados} atualizados, "
            f"{aposentados} antigos escondidos."
        )
    finally:
        db.close()


if __name__ == "__main__":
    run()
