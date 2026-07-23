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
    grant_comp_pro,
    retranslate_exercises,
    seed_exercisedb,
    seed_exercises,
    seed_exercises_open,
    seed_food_portions,
    seed_plant_based,
    seed_taco,
    seed_taco_official,
)


def _ensure_profile_columns() -> None:
    """ALTER idempotente (SQLite dev + Postgres prod) pras colunas novas de
    user_profiles: goal_pace, target_weight_kg e as preferências de treino do
    Coaching (weak_point, session_length, wants_cardio, periodization).
    Roda logo após o create_all, ANTES de qualquer select(UserProfile)."""
    from sqlalchemy import inspect, text

    existentes = {c["name"] for c in inspect(engine).get_columns("user_profiles")}
    add_cols = [
        ("goal_pace", "VARCHAR(10) NOT NULL DEFAULT 'NORMAL'", "VARCHAR(10) NOT NULL DEFAULT 'NORMAL'"),
        ("target_weight_kg", "DOUBLE PRECISION", "FLOAT"),
        # Preferências de treino do Coaching (o "cérebro de treino").
        ("weak_point", "VARCHAR(20)", "VARCHAR(20)"),
        ("weak_points", "VARCHAR(20)[]", "TEXT"),  # até 2 pontos fracos (lista)
        ("session_length", "VARCHAR(10)", "VARCHAR(10)"),
        ("wants_cardio", "BOOLEAN", "BOOLEAN"),
        ("periodization", "VARCHAR(12) NOT NULL DEFAULT 'auto'", "VARCHAR(12) NOT NULL DEFAULT 'auto'"),
        ("training_days_per_week", "INTEGER", "INTEGER"),
    ]
    pg = engine.dialect.name == "postgresql"
    with engine.begin() as conn:
        for col, pg_type, sqlite_type in add_cols:
            if col in existentes:
                continue
            if pg:
                conn.execute(text(f"ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS {col} {pg_type}"))
            else:
                conn.execute(text(f"ALTER TABLE user_profiles ADD COLUMN {col} {sqlite_type}"))


def _ensure_routine_exercise_columns() -> None:
    """ALTER idempotente pra set_intents (JSON) em routine_exercises — a
    intenção de cada série (até a falha / feeder) que o coach monta na rotina.
    Roda logo após o create_all, mesma regra das outras colunas novas."""
    from sqlalchemy import inspect, text

    existentes = {c["name"] for c in inspect(engine).get_columns("routine_exercises")}
    if "set_intents" in existentes:
        return
    pg = engine.dialect.name == "postgresql"
    with engine.begin() as conn:
        if pg:
            conn.execute(text("ALTER TABLE routine_exercises ADD COLUMN IF NOT EXISTS set_intents JSON"))
        else:
            conn.execute(text("ALTER TABLE routine_exercises ADD COLUMN set_intents JSON"))


def run() -> None:
    print(f"Criando schema em {engine.url} ...")
    Base.metadata.create_all(bind=engine)
    print("Schema pronto.")

    # ANTES de qualquer consulta a Exercise, e logo depois do create_all:
    # create_all não adiciona coluna em tabela que já existe, então num banco
    # antigo (produção) as colunas novas não existiriam — e QUALQUER
    # select(Exercise) do ORM já pede TODAS elas, estourando "no such column".
    # Como o start é `init_db && uvicorn`, isso não seria um erro de seed: o
    # backend inteiro não subiria (502). Estes passos têm que vir primeiro.
    #
    # ensure_columns() adiciona name_en/source_external_id/is_hidden (do
    # ExerciseDB) e PRECISA rodar aqui, não só dentro de seed_exercisedb.run()
    # lá no fim — senão o backfill_exercise_category abaixo já faz select(Exercise)
    # e derruba o boot antes do seed chegar a criar as colunas.
    seed_exercisedb.ensure_columns()
    backfill_exercise_category.run()

    # Colunas de medida caseira (unit_label/unit_amount) em meal_log_items e
    # saved_meal_items: mesmo motivo do ExerciseDB — precisam existir ANTES de a
    # API registrar qualquer refeição num banco antigo. A tabela food_portions é
    # nova, então o create_all acima já a cria; o backfill roda depois dos seeds.
    seed_food_portions.ensure_columns()

    # Ritmo do objetivo + peso-alvo em user_profiles: mesma regra — a API faz
    # select(UserProfile) o tempo todo, então num banco antigo essas colunas
    # PRECISAM existir antes de qualquer consulta, senão o boot morre (502).
    _ensure_profile_columns()

    # set_intents em routine_exercises — mesma regra (select(RoutineExercise)
    # roda o tempo todo em prod).
    _ensure_routine_exercise_columns()

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

    # Aplica o tradutor atual aos nomes já importados. Sem isto as correções do
    # tradutor só valeriam pra banco novo, e a produção ficaria com os nomes
    # quebrados ("Jerk two braço com kettlebell") pra sempre. Também é o que
    # desfaz os nomes duplicados (o importado que colide com um curado vira
    # "(variação N)"). Idempotente: só grava quando o nome muda de verdade.
    retranslate_exercises.run()

    # Base oficial do ExerciseDB (1394 com GIF próprio). Roda por ÚLTIMO e é
    # autoritativa: insere/atualiza os exercícios da ExerciseDB e ESCONDE a base
    # antiga (free-exercise-db) — sem apagar, pra não orfanar rotinas/histórico.
    # Idempotente e sem chamada de API (lê o snapshot versionado).
    seed_exercisedb.run()

    # Medidas caseiras embutidas (gramas/unidades): deriva uma FoodPortion do
    # default_portion de cada alimento. Depois dos seeds de comida, idempotente.
    seed_food_portions.run()

    # Pro de cortesia (testadores) via env PRO_COMP_EMAILS. Só concede.
    grant_comp_pro.run()

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
