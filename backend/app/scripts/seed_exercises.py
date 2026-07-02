"""Importa o seed local da biblioteca de exercícios. Idempotente (upsert por
nome). Uso: python -m app.scripts.seed_exercises

NOTA: app/data/exercise_seed.csv é um subconjunto curado (~50 exercícios)
cobrindo os principais grupos musculares e equipamentos, não a biblioteca de
600-1000 exercícios com vídeo recomendada na especificação (Parte 3.3/6).
Trocar por um banco licenciado (ExerciseDB, Ninjas API) ou produção própria
depois é só popular video_url nos registros existentes ou importar mais
linhas mantendo as mesmas colunas.
"""
import csv
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.exercise import Difficulty, Equipment, Exercise, MuscleGroup

CSV_PATH = Path(__file__).parent.parent / "data" / "exercise_seed.csv"


def run() -> None:
    db = SessionLocal()
    try:
        with CSV_PATH.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            created, updated = 0, 0
            for row in reader:
                existing = db.execute(
                    select(Exercise).where(
                        Exercise.name == row["name"], Exercise.is_custom.is_(False)
                    )
                ).scalar_one_or_none()

                secondary = [g for g in row["secondary_muscle_groups"].split(";") if g]

                fields = dict(
                    primary_muscle_group=MuscleGroup(row["primary_muscle_group"]),
                    secondary_muscle_groups=secondary,
                    equipment=Equipment(row["equipment"]),
                    difficulty=Difficulty(row["difficulty"]),
                    execution_text=row["execution_text"] or None,
                )

                if existing:
                    for key, value in fields.items():
                        setattr(existing, key, value)
                    updated += 1
                else:
                    db.add(Exercise(name=row["name"], is_custom=False, **fields))
                    created += 1

            db.commit()
            print(f"Exercícios seed: {created} criados, {updated} atualizados.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
