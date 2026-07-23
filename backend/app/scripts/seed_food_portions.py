"""Medidas caseiras dos alimentos (gramas/unidades da Parte 3.2).

Duas responsabilidades, ambas idempotentes e seguras em SQLite (dev) e Postgres
(prod):

1. `ensure_columns()` — adiciona unit_label/unit_amount em meal_log_items e
   saved_meal_items. create_all NÃO altera tabela que já existe, então num banco
   antigo essas colunas faltariam e qualquer registro de refeição estouraria.
   Roda cedo no init_db (antes de a API responder), como o padrão do ExerciseDB.

2. `run()` — cria a tabela food_portions (via create_all no init_db) e faz o
   BACKFILL: para cada alimento que já traz uma porção nomeada
   (default_portion_label + default_portion_g) e ainda não tem medida embutida,
   cria uma FoodPortion com o peso de UMA unidade. Assim ninguém perde a medida
   que já existia, e o app passa a oferecer "gramas OU <medida>".

Uso:  python -m app.scripts.seed_food_portions
"""

import re

from sqlalchemy import inspect, select, text

from app.core.db import SessionLocal, engine
from app.models.food import Food, FoodPortion

# Primeira palavra da medida no plural -> singular (espelha o pluralizar do app).
# "3 colheres de sopa" (45g) precisa virar a medida de UMA "colher de sopa" (15g).
_PLURAL_ES = ("r", "z")  # colheres->colher, cálices->cálice fica no ramo do 's'


def _singular_primeira(frase: str) -> str:
    palavras = frase.split()
    if not palavras:
        return frase
    w = palavras[0]
    if w.endswith("ões"):
        w = w[:-3] + "ão"
    elif w.endswith("es") and len(w) > 3 and w[-3] in _PLURAL_ES:
        w = w[:-2]  # colheres -> colher
    elif w.endswith("s") and len(w) > 2:
        w = w[:-1]  # conchas -> concha, fatias -> fatia, unidades -> unidade
    return " ".join([w, *palavras[1:]])


def parse_portion(label: str | None, portion_g: float | None) -> tuple[str, float] | None:
    """('3 colheres de sopa', 45.0) -> ('colher de sopa', 15.0).
    ('1 unidade', 50.0) -> ('unidade', 50.0). ('fatia', 25.0) -> ('fatia', 25.0).
    Retorna None quando não dá pra derivar uma medida útil."""
    if not label or not portion_g or portion_g <= 0:
        return None
    texto = label.strip()
    m = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s+(.*\S)\s*$", texto)
    if m:
        n = float(m.group(1).replace(",", "."))
        frase = m.group(2)
    else:
        n = 1.0
        frase = texto
    if n <= 0 or not frase:
        return None
    grams_one = portion_g / n
    if grams_one <= 0 or grams_one > 5000:
        return None
    if n != 1.0:
        frase = _singular_primeira(frase)
    # Rótulos genéricos demais ("porção", "medida") não ajudam — melhor só gramas.
    if frase.lower() in {"porção", "porcao", "medida", "g", "grama", "gramas"}:
        return None
    return frase[:50], round(grams_one, 2)


def ensure_columns() -> None:
    pg = engine.dialect.name == "postgresql"
    alvo = {
        "meal_log_items": {c["name"] for c in inspect(engine).get_columns("meal_log_items")},
        "saved_meal_items": {c["name"] for c in inspect(engine).get_columns("saved_meal_items")},
    }
    cols = [("unit_label", "VARCHAR(50)"), ("unit_amount", "DOUBLE PRECISION" if pg else "FLOAT")]
    with engine.begin() as conn:
        for tabela, existentes in alvo.items():
            for col, tipo in cols:
                if col in existentes:
                    continue
                if pg:
                    conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS {col} {tipo}"))
                else:
                    conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}"))


def run() -> None:
    # No init_db o create_all já criou food_portions antes daqui; rodando este
    # script sozinho (o uso documentado acima) a tabela pode não existir ainda.
    # checkfirst=True não recria se já estiver lá.
    FoodPortion.__table__.create(bind=engine, checkfirst=True)
    ensure_columns()
    db = SessionLocal()
    try:
        # Só alimentos que ainda não têm NENHUMA medida embutida (dono nulo).
        com_medida = set(
            db.execute(
                select(FoodPortion.food_id).where(FoodPortion.created_by_user_id.is_(None))
            ).scalars()
        )
        criadas = 0
        for food in db.execute(select(Food)).scalars():
            if food.id in com_medida:
                continue
            parsed = parse_portion(food.default_portion_label, food.default_portion_g)
            if parsed is None:
                continue
            label, grams = parsed
            db.add(
                FoodPortion(
                    food_id=food.id,
                    label=label,
                    grams=grams,
                    created_by_user_id=None,
                    sort_order=0,
                )
            )
            criadas += 1
        db.commit()
        print(f"Medidas caseiras embutidas criadas: {criadas}.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
