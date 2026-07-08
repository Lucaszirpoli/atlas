"""Adiciona a coluna foods.search_text no banco de dev (SQLite) se ainda não
existir e preenche todas as linhas com o nome+marca normalizados (sem acento).
Idempotente — pode rodar quantas vezes quiser.

    cd backend && .venv/Scripts/python -m app.scripts.backfill_search_text

Em produção (Postgres) a coluna vem pela migração Alembic 0008; este script é
só pra atualizar o appfit_dev.db que já existe sem recriar do zero.
"""

from sqlalchemy import inspect, text

from app.core.db import SessionLocal, engine
from app.core.text import normalize_search_text
from app.models.food import Food


def main() -> None:
    cols = [c["name"] for c in inspect(engine).get_columns("foods")]
    if "search_text" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE foods ADD COLUMN search_text VARCHAR(400) DEFAULT ''"))
        print("Coluna search_text criada.")

    db = SessionLocal()
    try:
        foods = db.query(Food).all()
        for food in foods:
            food.search_text = normalize_search_text(food.name, food.brand)
        db.commit()
        print(f"search_text preenchido em {len(foods)} alimentos.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
