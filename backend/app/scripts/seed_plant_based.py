"""Seed curado de alimentos plant-based / sem-alérgeno comuns no Brasil.

Motivo (crítica #2 da simulação): quem segue dieta vegana / restrita tinha 4x
mais chance de "não achei o alimento" (5,6% vs 1,4% geral) — a base TACO cobre
bem o genérico, mas faltavam os itens que esse público usa todo dia (tempeh,
seitan, leites vegetais, levedura nutricional, tahine, proteína vegana, etc.).

Macros por 100g de fontes de composição consagradas (USDA/TACO/rótulos médios
BR). Idempotente por external_id. Fonte TACO (é dado local curado, não marca).

Uso: python -m app.scripts.seed_plant_based
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.food import Food, FoodSource

# (external_id, nome, kcal, prot, carb, gord, fibra, porção_g, rótulo_porção)
FOODS: list[tuple] = [
    # --- proteínas vegetais ---
    ("pb_tofu_firme", "Tofu firme", 144, 15.8, 2.8, 8.7, 2.3, 100, "fatia"),
    ("pb_tofu_defumado", "Tofu defumado", 145, 16.0, 2.0, 8.5, 2.0, 100, "fatia"),
    ("pb_tempeh", "Tempeh", 192, 20.3, 7.6, 10.8, 0.0, 100, "fatia"),
    ("pb_seitan", "Seitan (glúten de trigo)", 121, 24.0, 4.0, 1.9, 0.6, 100, "porção"),
    ("pb_pts_seca", "Carne de soja / proteína texturizada (seca)", 336, 52.0, 30.0, 1.5, 18.0, 25, "porção seca"),
    ("pb_pts_hidratada", "Carne de soja / proteína texturizada (hidratada)", 108, 17.0, 9.0, 0.5, 6.0, 100, "porção"),
    ("pb_edamame", "Edamame (soja verde)", 121, 11.9, 8.9, 5.2, 5.2, 100, "porção"),
    ("pb_grao_bico_cozido", "Grão-de-bico cozido", 164, 8.9, 27.4, 2.6, 7.6, 120, "concha"),
    ("pb_lentilha_cozida", "Lentilha cozida", 116, 9.0, 20.1, 0.4, 7.9, 100, "concha"),
    ("pb_ervilha_cozida", "Ervilha cozida", 84, 5.4, 15.6, 0.4, 5.5, 100, "porção"),
    ("pb_feijao_branco_cozido", "Feijão branco cozido", 139, 9.7, 25.0, 0.5, 6.3, 100, "concha"),
    ("pb_hamburguer_vegetal", "Hambúrguer vegetal (à base de plantas)", 220, 17.0, 5.0, 14.0, 3.0, 113, "unidade"),
    ("pb_salsicha_vegana", "Salsicha vegana", 230, 17.0, 5.0, 16.0, 2.0, 50, "unidade"),
    ("pb_almondega_vegetal", "Almôndega vegetal", 200, 15.0, 9.0, 11.0, 4.0, 30, "unidade"),
    # --- leites e iogurtes vegetais ---
    ("pb_leite_soja", "Leite de soja (sem açúcar)", 54, 3.3, 6.0, 1.8, 0.6, 200, "copo"),
    ("pb_leite_amendoas", "Leite de amêndoas (sem açúcar)", 15, 0.6, 0.3, 1.1, 0.4, 200, "copo"),
    ("pb_leite_aveia", "Leite de aveia", 46, 1.0, 7.0, 1.5, 0.8, 200, "copo"),
    ("pb_leite_coco_bebida", "Leite de coco (bebida)", 20, 0.2, 0.6, 2.0, 0.0, 200, "copo"),
    ("pb_leite_arroz", "Leite de arroz", 47, 0.3, 9.2, 1.0, 0.3, 200, "copo"),
    ("pb_leite_sem_lactose", "Leite sem lactose (integral)", 42, 3.3, 4.9, 1.0, 0.0, 200, "copo"),
    ("pb_iogurte_coco", "Iogurte de coco", 97, 1.0, 8.0, 7.0, 0.5, 120, "pote"),
    ("pb_iogurte_soja", "Iogurte de soja", 50, 4.0, 5.0, 2.0, 0.5, 120, "pote"),
    # --- pós de proteína vegana ---
    ("pb_proteina_vegana", "Proteína vegana (ervilha/arroz)", 375, 80.0, 6.0, 5.0, 3.0, 30, "scoop"),
    ("pb_proteina_ervilha", "Proteína isolada de ervilha", 385, 82.0, 3.0, 6.0, 2.0, 30, "scoop"),
    # --- pastas, sementes e castanhas (sem lactose/veganas) ---
    ("pb_levedura_nutricional", "Levedura nutricional", 385, 50.0, 36.0, 4.0, 20.0, 10, "colher"),
    ("pb_tahine", "Tahine (pasta de gergelim)", 595, 17.0, 21.2, 53.8, 9.3, 15, "colher"),
    ("pb_homus", "Homus (pasta de grão-de-bico)", 177, 7.9, 20.1, 8.6, 6.0, 30, "colher"),
    ("pb_pasta_amendoim", "Pasta de amendoim integral", 588, 25.1, 20.0, 50.0, 6.0, 20, "colher"),
    ("pb_castanha_caju", "Castanha de caju", 553, 18.2, 30.2, 43.9, 3.3, 30, "punhado"),
    ("pb_castanha_para", "Castanha-do-pará", 656, 14.3, 12.3, 66.4, 7.5, 20, "unidades"),
    ("pb_amendoas", "Amêndoas", 579, 21.2, 21.6, 49.9, 12.5, 30, "punhado"),
    ("pb_nozes", "Nozes", 654, 15.2, 13.7, 65.2, 6.7, 30, "punhado"),
    ("pb_semente_girassol", "Semente de girassol", 584, 20.8, 20.0, 51.5, 8.6, 20, "colher"),
    ("pb_semente_abobora", "Semente de abóbora", 559, 30.2, 10.7, 49.1, 6.0, 20, "colher"),
    ("pb_linhaca", "Linhaça", 534, 18.3, 28.9, 42.2, 27.3, 15, "colher"),
    # --- farinhas sem glúten (alérgicos) ---
    ("pb_farinha_amendoas", "Farinha de amêndoas", 571, 21.4, 20.0, 50.0, 11.0, 30, "porção"),
    ("pb_farinha_coco", "Farinha de coco", 400, 18.0, 60.0, 13.0, 39.0, 15, "colher"),
    ("pb_farinha_arroz", "Farinha de arroz", 366, 5.9, 80.1, 1.4, 2.4, 30, "porção"),
    ("pb_polvilho_doce", "Polvilho doce (fécula de mandioca)", 351, 0.4, 87.0, 0.1, 1.0, 30, "porção"),
    # --- outros veganos comuns ---
    ("pb_queijo_vegano", "Queijo vegano", 280, 1.0, 23.0, 20.0, 1.0, 30, "fatia"),
    ("pb_margarina_vegana", "Margarina vegetal", 717, 0.2, 0.7, 81.0, 0.0, 10, "colher"),
    ("pb_champignon", "Cogumelo champignon", 22, 3.1, 3.3, 0.3, 1.0, 80, "porção"),
    ("pb_shiitake", "Cogumelo shiitake", 34, 2.2, 6.8, 0.5, 2.5, 80, "porção"),
    ("pb_miso", "Missô (pasta de soja)", 199, 11.7, 26.5, 6.0, 5.4, 15, "colher"),
    ("pb_leite_condensado_coco", "Leite condensado de coco", 290, 1.5, 55.0, 8.0, 0.5, 20, "colher"),
]


def run() -> None:
    db = SessionLocal()
    try:
        created, updated = 0, 0
        for ext, name, kcal, p, c, f, fib, portion, label in FOODS:
            existing = db.execute(
                select(Food).where(Food.source == FoodSource.TACO, Food.external_id == ext)
            ).scalar_one_or_none()
            fields = dict(
                name=name,
                kcal_per_100g=float(kcal),
                protein_g_per_100g=float(p),
                carbs_g_per_100g=float(c),
                fat_g_per_100g=float(f),
                fiber_g_per_100g=float(fib),
                default_portion_g=float(portion),
                default_portion_label=label,
            )
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(Food(source=FoodSource.TACO, external_id=ext, **fields))
                created += 1
        db.commit()
        print(f"Plant-based / sem-alérgeno: {created} criados, {updated} atualizados.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
