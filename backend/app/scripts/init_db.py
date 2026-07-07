"""Bootstrap do banco para dev local (SQLite, sem servidor Postgres).

Cria todas as tabelas a partir dos modelos (sem Alembic — o schema atual dos
modelos já inclui tudo, inclusive ai_free_credits) e roda os seeds só quando as
tabelas de alimentos/exercícios estão vazias, então é seguro rodar de novo.

Uso:  python -m app.scripts.init_db
"""

import app.models  # noqa: F401  (importa todos os modelos p/ popular o metadata)
from app.core.db import Base, SessionLocal, engine
from app.models.exercise import Exercise
from app.models.food import Food
from app.scripts import (
    seed_exercises,
    seed_exercises_open,
    seed_taco,
    seed_taco_official,
)


def run() -> None:
    print(f"Criando schema em {engine.url} ...")
    Base.metadata.create_all(bind=engine)
    print("Schema pronto.")

    db = SessionLocal()
    try:
        food_count = db.query(Food).count()
        exercise_count = db.query(Exercise).count()
    finally:
        db.close()

    if food_count == 0:
        print("Base de alimentos vazia — carregando seeds TACO ...")
        seed_taco.run()
        seed_taco_official.run()
    else:
        print(f"Alimentos já carregados ({food_count}) — pulando seed.")

    if exercise_count == 0:
        print("Base de exercícios vazia — carregando seeds ...")
        seed_exercises.run()
        seed_exercises_open.run()
    else:
        print(f"Exercícios já carregados ({exercise_count}) — pulando seed.")

    print("init_db concluído.")


if __name__ == "__main__":
    run()
