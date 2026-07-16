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
    backfill_exercise_category,
    seed_exercises,
    seed_exercises_open,
    seed_plant_based,
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
        seed_plant_based.run()  # cobertura vegana / sem-alérgeno (crítica #2)
    else:
        print(f"Alimentos já carregados ({food_count}) — pulando seed.")
        # idempotente: garante os plant-based mesmo em banco já existente
        seed_plant_based.run()

    if exercise_count == 0:
        print("Base de exercícios vazia — carregando seeds ...")
        seed_exercises.run()
        seed_exercises_open.run()
    else:
        print(f"Exercícios já carregados ({exercise_count}) — pulando seed.")

    _wire_local_exercise_images()

    # Idempotente e OBRIGATÓRIO em banco já existente: create_all não adiciona
    # coluna em tabela que já existe, então a categoria (que separa musculação
    # de alongamento/cardio) precisa deste passo explícito pra chegar na prod.
    backfill_exercise_category.run()

    print("init_db concluído.")


def _wire_local_exercise_images() -> None:
    """Liga cada exercício curado ao seu GIF local (baixado da ExerciseDB e
    versionado em app/static/exercise_images/{id}.gif) usando uma URL RELATIVA
    ("/static/..."). O app mobile prefixa o endereço do backend na hora de
    exibir — assim as imagens funcionam em qualquer host (dev, Railway, etc.)
    sem depender de um endereço fixo gravado no banco. Idempotente.
    """
    from pathlib import Path

    from sqlalchemy import select

    images_dir = Path(__file__).parent.parent / "static" / "exercise_images"
    if not images_dir.exists():
        return

    db = SessionLocal()
    try:
        wired = 0
        for gif in images_dir.glob("*.gif"):
            try:
                ex_id = int(gif.stem)
            except ValueError:
                continue
            ex = db.execute(select(Exercise).where(Exercise.id == ex_id)).scalar_one_or_none()
            if ex is None:
                continue
            rel = f"/static/exercise_images/{ex_id}.gif"
            if ex.video_url != rel:
                ex.video_url = rel
                wired += 1
        db.commit()
        if wired:
            print(f"Imagens locais de exercício ligadas: {wired}.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
