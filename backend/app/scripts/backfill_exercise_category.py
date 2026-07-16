"""Cria e preenche exercises.category em banco já existente (dev e produção).

POR QUE ISSO EXISTE: o seed do free-exercise-db nunca leu o campo `category`
da fonte, então 292 dos 873 registros importados (123 alongamentos, 61
pliometrias, 21 strongman, 14 cardio) entraram indistinguíveis de musculação.
Resultado real em produção: a engine montava "treino de pernas" com
"All Fours Quad Stretch" (um alongamento) e "Ankle Circles" (mobilidade).

O deploy roda `init_db`, que só faz `create_all` — e create_all NÃO adiciona
coluna em tabela que já existe. Por isso o ALTER TABLE aqui é explícito.

Idempotente: pode rodar em todo deploy.

Uso: python -m app.scripts.backfill_exercise_category
"""

import json

from sqlalchemy import inspect, select, text

from app.core.db import SessionLocal, engine
from app.models.exercise import Exercise, ExerciseCategory, MuscleGroup
from app.scripts.seed_exercises_open import IMAGE_BASE, JSON_PATH

# Categoria da fonte -> a nossa. A fonte usa "olympic weightlifting" com espaço.
_SOURCE_MAP = {
    "strength": ExerciseCategory.STRENGTH,
    "powerlifting": ExerciseCategory.POWERLIFTING,
    "olympic weightlifting": ExerciseCategory.OLYMPIC,
    "strongman": ExerciseCategory.STRONGMAN,
    "plyometrics": ExerciseCategory.PLYOMETRICS,
    "stretching": ExerciseCategory.STRETCHING,
    "cardio": ExerciseCategory.CARDIO,
}

# Curados (CSV) não têm categoria na origem — classificados por nome. Só o que
# NÃO é musculação precisa aparecer aqui; o resto cai no default STRENGTH.
_CURATED_CARDIO = (
    "corrida", "esteira", "caminhada", "bicicleta", "bike", "elíptico", "eliptico",
    "remo ergômetro", "remo ergometro", "escada", "stair", "pular corda", "hiit",
    "natação", "natacao", "polichinelo", "sprint",
)
_CURATED_STRETCHING = ("alongamento", "mobilidade", "giro de bastão", "giro de bastao")
_CURATED_PLYO = ("box jump", "salto", "wall ball")


def _column_exists() -> bool:
    return any(c["name"] == "category" for c in inspect(engine).get_columns("exercises"))


def _add_column() -> None:
    """ALTER TABLE explícito: funciona igual em SQLite (dev) e Postgres (prod).

    ATENÇÃO ao formato: o tipo Enum do SQLAlchemy grava o NOME do membro, não o
    .value — as outras colunas do projeto guardam 'CHEST', 'BARBELL',
    'INTERMEDIATE'. Um DEFAULT 'strength' (minúsculo) faz a leitura estourar
    LookupError. Por isso os rótulos aqui são os nomes, em maiúsculas.
    """
    labels = ", ".join(f"'{c.name}'" for c in ExerciseCategory)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(
                text(
                    "DO $$ BEGIN "
                    f"CREATE TYPE exercise_category AS ENUM ({labels}); "
                    "EXCEPTION WHEN duplicate_object THEN null; END $$;"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE exercises ADD COLUMN IF NOT EXISTS category "
                    "exercise_category NOT NULL DEFAULT 'STRENGTH'"
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_exercises_category ON exercises (category)"))
    else:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE exercises ADD COLUMN category VARCHAR(21) NOT NULL DEFAULT 'STRENGTH'")
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_exercises_category ON exercises (category)"))


def _classify_curated(ex: Exercise) -> ExerciseCategory:
    name = (ex.name or "").lower()
    # Sinal mais forte que o nome: os curados de cardio já vêm com o grupo CARDIO.
    if ex.primary_muscle_group == MuscleGroup.CARDIO:
        return ExerciseCategory.CARDIO
    if any(k in name for k in _CURATED_CARDIO):
        return ExerciseCategory.CARDIO
    if any(k in name for k in _CURATED_STRETCHING):
        return ExerciseCategory.STRETCHING
    if any(k in name for k in _CURATED_PLYO):
        return ExerciseCategory.PLYOMETRICS
    return ExerciseCategory.STRENGTH


def run() -> None:
    if not _column_exists():
        print("Coluna exercises.category ausente — criando ...")
        _add_column()
        print("Coluna criada.")

    # Casa o registro importado com a fonte pelo caminho da imagem (é único por
    # exercício), que é exatamente o que o seed usou pra montar a video_url.
    by_image: dict[str, str] = {}
    for row in json.loads(JSON_PATH.read_text(encoding="utf-8")):
        images = row.get("images") or []
        cat = row.get("category")
        if images and cat:
            by_image[images[0]] = cat

    db = SessionLocal()
    try:
        changed = 0
        counts: dict[str, int] = {}
        for ex in db.execute(select(Exercise)).scalars():
            if ex.video_url and ex.video_url.startswith(IMAGE_BASE):
                src = by_image.get(ex.video_url[len(IMAGE_BASE) :])
                cat = _SOURCE_MAP.get(src or "", ExerciseCategory.STRENGTH)
            else:
                cat = _classify_curated(ex)
            counts[cat.value] = counts.get(cat.value, 0) + 1
            if ex.category != cat:
                ex.category = cat
                changed += 1
        db.commit()
        print(f"Categorias preenchidas ({changed} alterados):")
        for k in sorted(counts, key=lambda x: -counts[x]):
            print(f"  {k:<22} {counts[k]:>4}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
