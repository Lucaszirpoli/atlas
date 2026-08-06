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
    dedup_foods,
    backfill_exercise_category,
    clean_taco_names,
    grant_comp_pro,
    retranslate_exercises,
    seed_exercisedb,
    seed_exercises,
    seed_exercises_curated,
    seed_exercises_open,
    seed_food_portions,
    seed_medidas_caseiras,
    seed_plant_based,
    seed_taco,
    seed_taco_official,
)


def _ensure_profile_columns() -> None:
    """ALTER idempotente (SQLite dev + Postgres prod) pras colunas novas de
    user_profiles: goal_pace, target_weight_kg e as preferências de treino do
    Coaching (weak_point, session_length, periodization).
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
        ("session_includes_cardio", "BOOLEAN", "BOOLEAN"),
        ("periodization", "VARCHAR(12) NOT NULL DEFAULT 'auto'", "VARCHAR(12) NOT NULL DEFAULT 'auto'"),
        ("training_days_per_week", "INTEGER", "INTEGER"),
        # Fuso do aparelho — define o dia de calendário de cada registro.
        ("timezone", "VARCHAR(64)", "VARCHAR(64)"),
        # Deixa o coach usar técnica avançada? NULL = perfil que nunca
        # respondeu; a regra de segurança nega pra iniciante.
        ("allow_advanced_techniques", "BOOLEAN", "BOOLEAN"),
        # Respostas do questionário que antes eram descartadas.
        ("exercise_prefs", "VARCHAR(40)[]", "TEXT"),
        ("exercise_preferences_text", "TEXT", "TEXT"),
        ("training_history", "TEXT", "TEXT"),
        ("food_dislikes", "TEXT", "TEXT"),
        ("medications", "TEXT", "TEXT"),
        ("extra_notes", "TEXT", "TEXT"),
        ("strong_points", "VARCHAR(20)[]", "TEXT"),
        # Quando o bloco de especialização (ponto fraco) começou — o relógio que
        # faz o coach cobrar a revisão em vez de deixar a priorização eterna.
        ("weak_points_since", "TIMESTAMPTZ", "TIMESTAMP"),
        # Respostas ESTRUTURADAS do questionário novo, que substituíram os campos
        # de texto livre. Cada uma tem um consumidor determinístico no motor —
        # ver o bloco correspondente em models/user_profile.py.
        ("training_time", "VARCHAR(12)", "VARCHAR(12)"),
        ("rir_accuracy", "VARCHAR(16)", "VARCHAR(16)"),
        ("has_injury", "BOOLEAN", "BOOLEAN"),
        ("injury_regions", "VARCHAR(16)[]", "TEXT"),
        ("medical_clearance", "BOOLEAN", "BOOLEAN"),
        ("has_pain", "BOOLEAN", "BOOLEAN"),
        ("pain_regions", "VARCHAR(16)[]", "TEXT"),
        ("pain_intensity", "VARCHAR(12)", "VARCHAR(12)"),
        ("limitations", "VARCHAR(20)[]", "TEXT"),
        ("gym_crowding", "VARCHAR(10)", "VARCHAR(10)"),
        ("home_equipment", "VARCHAR(20)[]", "TEXT"),
        ("split_preference", "VARCHAR(16)", "VARCHAR(16)"),
        ("avoid_mixing_upper_lower", "BOOLEAN", "BOOLEAN"),
        ("load_preference", "VARCHAR(12)", "VARCHAR(12)"),
        ("failure_comfort", "VARCHAR(12)", "VARCHAR(12)"),
        ("sleep_quality", "VARCHAR(8)", "VARCHAR(8)"),
        ("stress_level", "VARCHAR(8)", "VARCHAR(8)"),
        ("recovery_between", "VARCHAR(12)", "VARCHAR(12)"),
        ("other_sport", "VARCHAR(10)", "VARCHAR(10)"),
        ("food_dislikes_list", "VARCHAR(30)[]", "TEXT"),
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


def _ensure_user_columns() -> None:
    """ALTER idempotente pras colunas de 'esqueci minha senha' em users
    (reset_code_hash, reset_code_expires_at). Mesma regra: select(User) roda
    em todo login, então precisam existir antes de qualquer consulta."""
    from sqlalchemy import inspect, text

    existentes = {c["name"] for c in inspect(engine).get_columns("users")}
    add_cols = [
        ("reset_code_hash", "VARCHAR(255)", "VARCHAR(255)"),
        ("reset_code_expires_at", "TIMESTAMPTZ", "TIMESTAMP"),
    ]
    pg = engine.dialect.name == "postgresql"
    with engine.begin() as conn:
        for col, pg_type, sqlite_type in add_cols:
            if col in existentes:
                continue
            if pg:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {pg_type}"))
            else:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {sqlite_type}"))


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


def _ensure_routine_columns() -> None:
    """ALTER idempotente pra `routines.origem` ("coach" | "manual") — quem
    montou a rotina. Mesma regra das outras colunas novas: select(Routine) roda
    o tempo todo, então num banco antigo ela precisa existir antes de qualquer
    consulta, senão o boot morre.

    Faz também o BACKFILL de quem já existe: rotina antiga nasceria "manual" e
    as fichas que o coach montou perderiam a prescrição fechada. Quem preenche
    `set_intents` é só o montador do coach — rotina feita à mão ou importada
    fica com `[]` —, então essa é a marca de origem confiável no que já está
    gravado."""
    from sqlalchemy import inspect, text

    existentes = {c["name"] for c in inspect(engine).get_columns("routines")}
    if "origem" in existentes:
        return
    pg = engine.dialect.name == "postgresql"
    with engine.begin() as conn:
        if pg:
            conn.execute(
                text(
                    "ALTER TABLE routines ADD COLUMN IF NOT EXISTS origem "
                    "VARCHAR(10) NOT NULL DEFAULT 'manual'"
                )
            )
            marca = (
                "UPDATE routines SET origem = 'coach' WHERE id IN ("
                "SELECT routine_id FROM routine_exercises "
                "WHERE set_intents IS NOT NULL AND set_intents::text NOT IN ('[]', 'null'))"
            )
        else:
            conn.execute(
                text("ALTER TABLE routines ADD COLUMN origem VARCHAR(10) NOT NULL DEFAULT 'manual'")
            )
            marca = (
                "UPDATE routines SET origem = 'coach' WHERE id IN ("
                "SELECT routine_id FROM routine_exercises "
                "WHERE set_intents IS NOT NULL AND set_intents NOT IN ('[]', 'null'))"
            )
        conn.execute(text(marca))


def _ensure_set_log_columns() -> None:
    """ALTER idempotente pras colunas de BLOCO em workout_set_logs (técnicas
    avançadas: myo-reps, cluster, rest-pause, drop-set). Mesma regra das
    outras: select(WorkoutSetLog) roda o tempo todo, então num banco antigo
    essas colunas precisam existir antes de qualquer consulta."""
    from sqlalchemy import inspect, text

    existentes = {c["name"] for c in inspect(engine).get_columns("workout_set_logs")}
    add_cols = [("block_index", "INTEGER", "INTEGER"), ("block_status", "VARCHAR(12)", "VARCHAR(12)")]
    pg = engine.dialect.name == "postgresql"
    with engine.begin() as conn:
        for col, pg_type, sqlite_type in add_cols:
            if col in existentes:
                continue
            if pg:
                conn.execute(text(f"ALTER TABLE workout_set_logs ADD COLUMN IF NOT EXISTS {col} {pg_type}"))
            else:
                conn.execute(text(f"ALTER TABLE workout_set_logs ADD COLUMN {col} {sqlite_type}"))


def _ensure_food_source_enum() -> None:
    """`foods.source` é um ENUM nativo no Postgres — `create_all` não adiciona
    valor novo a um tipo que já existe. Sem isto, gravar um Food com
    source=FATSECRET (a integração nova) derruba com "invalid input value for
    enum food_source" em produção. SQLite (dev) não tem enum nativo — é só
    VARCHAR — então não precisa disto."""
    if engine.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    # ALTER TYPE ... ADD VALUE não pode rodar dentro de uma transação que
    # também vá usar o valor novo — autocommit evita isso.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("ALTER TYPE food_source ADD VALUE IF NOT EXISTS 'fatsecret'"))


def _ensure_food_columns() -> None:
    """ALTER idempotente pra `foods.hidden` (usada pra suprimir o gêmeo
    perdedor de um alimento duplicado — ver o comentário no modelo). Mesma
    regra das outras: select(Food)/count(Food) roda logo no boot, então num
    banco antigo a coluna precisa existir ANTES dessa consulta, senão o boot
    inteiro morre (502)."""
    from sqlalchemy import inspect, text

    existentes = {c["name"] for c in inspect(engine).get_columns("foods")}
    if "hidden" in existentes:
        return
    pg = engine.dialect.name == "postgresql"
    with engine.begin() as conn:
        if pg:
            conn.execute(text("ALTER TABLE foods ADD COLUMN IF NOT EXISTS hidden BOOLEAN NOT NULL DEFAULT false"))
        else:
            conn.execute(text("ALTER TABLE foods ADD COLUMN hidden BOOLEAN NOT NULL DEFAULT 0"))


def run() -> None:
    print(f"Criando schema em {engine.url} ...")
    Base.metadata.create_all(bind=engine)
    print("Schema pronto.")

    _ensure_food_source_enum()
    _ensure_food_columns()

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

    # reset_code_hash/reset_code_expires_at em users — mesma regra.
    _ensure_user_columns()

    # set_intents em routine_exercises — mesma regra (select(RoutineExercise)
    # roda o tempo todo em prod).
    _ensure_routine_exercise_columns()

    # origem ("coach"/"manual") em routines — mesma regra, e com backfill de
    # quem já existe (ver a função).
    _ensure_routine_columns()

    # Blocos das técnicas avançadas em workout_set_logs — mesma regra.
    _ensure_set_log_columns()

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

    # Nomes do TACO oficial vieram no formato bruto de tabela ("Arroz,
    # integral, cozido") — roda sempre (idempotente, só mexe em nome com
    # vírgula) pra também corrigir banco já existente, não só banco novo.
    clean_taco_names.run()

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

    # Biblioteca curada (117 exercícios pedidos): roda por ÚLTIMO, DEPOIS do
    # seed_exercisedb, porque ele esconde a base antiga — e este seed força
    # is_hidden=False, garantindo que os 117 fiquem visíveis na busca/motor.
    # Idempotente (upsert por nome), então roda em todo boot sem duplicar.
    seed_exercises_curated.run()

    # Medidas caseiras embutidas (gramas/unidades): deriva uma FoodPortion do
    # default_portion de cada alimento. Depois dos seeds de comida, idempotente.
    seed_food_portions.run()

    # Medidas caseiras CURADAS + supressão de alimentos repetidos. Roda DEPOIS
    # do seed_food_portions de propósito: aquele deriva a medida do próprio
    # alimento (fonte melhor) e este só preenche quem ficou sem nenhuma.
    seed_medidas_caseiras.run()

    # Limpeza dos alimentos: homônimo sem marca, duplicata que só muda o sal,
    # nome ambíguo ao lado de versões específicas, e genérico de uma palavra.
    # Roda por ÚLTIMO entre os seeds de comida, porque precisa da base completa
    # pra decidir quem é duplicata de quem. ESCONDE, nunca apaga — o histórico
    # de refeições referencia food_id por FK (regra 4). Idempotente.
    dedup_foods.run()

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
