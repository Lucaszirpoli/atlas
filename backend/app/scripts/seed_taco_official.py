"""Importa a TACO oficial completa (Tabela Brasileira de Composição de
Alimentos, UNICAMP — 597 itens) a partir do JSON aberto em
app/data/taco_official.json. Idempotente (upsert por external_id).

Uso: python -m app.scripts.seed_taco_official

Esses itens são a referência oficial "in natura / cru / preparo básico".
Convivem com o seed curado (app/data/taco_seed.csv), que traz pratos prontos
e porções caseiras nomeadas que a TACO crua não tem. A TACO não quebra o
açúcar dos carboidratos, então sugar_g_per_100g fica nulo nesses itens.
"""
import json
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.food import Food, FoodSource

JSON_PATH = Path(__file__).parent.parent / "data" / "taco_official.json"


def _num(value) -> float | None:
    """Converte valores da TACO: 'Tr' (traço) -> 0, 'NA'/''/None -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    v = str(value).strip()
    if v in ("", "NA", "*"):
        return None
    if v.lower() in ("tr",):
        return 0.0
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def run() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        created, updated, skipped = 0, 0, 0
        for row in data:
            kcal = _num(row.get("energy_kcal"))
            protein = _num(row.get("protein_g"))
            carbs = _num(row.get("carbohydrate_g"))
            fat = _num(row.get("lipid_g"))
            # Sem energia ou macros essenciais não faz sentido no app.
            if kcal is None or protein is None or carbs is None or fat is None:
                skipped += 1
                continue

            external_id = f"TACO-OFF-{row['id']}"
            existing = db.execute(
                select(Food).where(
                    Food.source == FoodSource.TACO, Food.external_id == external_id
                )
            ).scalar_one_or_none()

            fields = dict(
                name=row["description"],
                kcal_per_100g=round(kcal, 1),
                protein_g_per_100g=round(protein, 1),
                carbs_g_per_100g=round(carbs, 1),
                fat_g_per_100g=round(fat, 1),
                fiber_g_per_100g=_num(row.get("fiber_g")),
                sodium_mg_per_100g=_num(row.get("sodium_mg")),
                sugar_g_per_100g=None,
                default_portion_g=100.0,
                default_portion_label="100 g (referência TACO)",
            )

            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(Food(source=FoodSource.TACO, external_id=external_id, **fields))
                created += 1

        db.commit()
        print(f"TACO oficial: {created} criados, {updated} atualizados, {skipped} pulados.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
