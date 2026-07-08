"""Adiciona a coluna exercises.is_compound no banco de dev (SQLite) se ainda
não existir e classifica todos os exercícios (composto vs isolado). Idempotente.

    cd backend && .venv/Scripts/python -m app.scripts.backfill_is_compound
"""

from sqlalchemy import inspect, text

from app.core.db import SessionLocal, engine
from app.models.exercise import Exercise
from app.services.exercise_classify import classify_is_compound


def main() -> None:
    cols = [c["name"] for c in inspect(engine).get_columns("exercises")]
    if "is_compound" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE exercises ADD COLUMN is_compound BOOLEAN DEFAULT 1"))
        print("Coluna is_compound criada.")

    db = SessionLocal()
    try:
        exercises = db.query(Exercise).all()
        comp = 0
        for ex in exercises:
            ex.is_compound = classify_is_compound(ex.name, ex.secondary_muscle_groups, ex.equipment)
            comp += 1 if ex.is_compound else 0
        db.commit()
        print(f"{len(exercises)} exercícios classificados: {comp} compostos, {len(exercises) - comp} isolados.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
