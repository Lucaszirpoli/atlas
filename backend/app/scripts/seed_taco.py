"""Importa o seed local da TACO (Tabela Brasileira de Composição de Alimentos)
para o Postgres. Idempotente: roda de novo sem duplicar (upsert por external_id).

Uso: python -m app.scripts.seed_taco

NOTA: app/data/taco_seed.csv é um subconjunto curado (~40 itens) cobrindo os
alimentos mais comuns citados na especificação do produto, não a tabela TACO
oficial completa da UNICAMP (que tem ~600 itens). Trocar por o CSV oficial
completo é so substituir o arquivo mantendo as mesmas colunas.
"""
import csv
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.food import Food, FoodSource

CSV_PATH = Path(__file__).parent.parent / "data" / "taco_seed.csv"


def run() -> None:
    db = SessionLocal()
    try:
        with CSV_PATH.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            created, updated = 0, 0
            for row in reader:
                existing = db.execute(
                    select(Food).where(
                        Food.source == FoodSource.TACO, Food.external_id == row["external_id"]
                    )
                ).scalar_one_or_none()

                fields = dict(
                    name=row["name"],
                    kcal_per_100g=float(row["kcal_per_100g"]),
                    protein_g_per_100g=float(row["protein_g_per_100g"]),
                    carbs_g_per_100g=float(row["carbs_g_per_100g"]),
                    fat_g_per_100g=float(row["fat_g_per_100g"]),
                    fiber_g_per_100g=float(row["fiber_g_per_100g"]) if row["fiber_g_per_100g"] else None,
                    sodium_mg_per_100g=float(row["sodium_mg_per_100g"]) if row["sodium_mg_per_100g"] else None,
                    sugar_g_per_100g=float(row["sugar_g_per_100g"]) if row["sugar_g_per_100g"] else None,
                    default_portion_g=float(row["default_portion_g"]),
                    default_portion_label=row["default_portion_label"] or None,
                )

                if existing:
                    for key, value in fields.items():
                        setattr(existing, key, value)
                    updated += 1
                else:
                    db.add(
                        Food(
                            source=FoodSource.TACO,
                            external_id=row["external_id"],
                            **fields,
                        )
                    )
                    created += 1

            db.commit()
            print(f"TACO seed: {created} criados, {updated} atualizados.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
