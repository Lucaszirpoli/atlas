"""Cálculo de meta calórica automática: TMB por Mifflin-St Jeor + fator de
atividade + ajuste por objetivo. Referência citada na especificação (seção
3.2) como a fórmula mais precisa disponível hoje, mais confiável que
Harris-Benedict."""

from app.models.user_profile import ActivityLevel, BiologicalSex, Goal, GoalPace

ACTIVITY_FACTORS: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}

# Ajuste percentual sobre o TDEE conforme objetivo. Déficit/superávit
# moderados, dentro do que a literatura considera sustentável.
GOAL_KCAL_ADJUSTMENT: dict[Goal, float] = {
    Goal.EMAGRECIMENTO: -0.20,
    Goal.HIPERTROFIA: 0.10,
    Goal.MANUTENCAO: 0.0,
    Goal.PERFORMANCE: 0.05,
    Goal.RECOMPOSICAO: -0.10,
}

# Ritmo escala o déficit/superávit: devagar = mais suave (mais tempo, menos
# risco), rápido = mais agressivo. 'normal' = o recomendado (multiplicador 1).
PACE_MULTIPLIER: dict[GoalPace, float] = {
    GoalPace.SLOW: 0.6,
    GoalPace.NORMAL: 1.0,
    GoalPace.FAST: 1.4,
}

# Objetivos em que o ritmo faz sentido (têm ganho/perda de peso deliberado).
PACE_APPLIES: set[Goal] = {Goal.EMAGRECIMENTO, Goal.HIPERTROFIA, Goal.RECOMPOSICAO}

KCAL_PER_KG_BODY = 7700.0  # ~kcal por kg de peso corporal (aprox. clássica)

# g de proteína por kg de peso corporal, por objetivo.
GOAL_PROTEIN_G_PER_KG: dict[Goal, float] = {
    Goal.EMAGRECIMENTO: 2.0,
    Goal.HIPERTROFIA: 1.8,
    Goal.MANUTENCAO: 1.6,
    Goal.PERFORMANCE: 1.8,
    Goal.RECOMPOSICAO: 2.0,
}

FAT_KCAL_FRACTION = 0.25
KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_CARB = 4
KCAL_PER_G_FAT = 9


def calculate_bmr(
    biological_sex: BiologicalSex, weight_kg: float, height_cm: float, age: int
) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + (5 if biological_sex == BiologicalSex.MALE else -161)


def calculate_tdee(bmr: float, activity_level: ActivityLevel) -> float:
    return bmr * ACTIVITY_FACTORS[activity_level]


def goal_adjustment_for(goal: Goal, pace: GoalPace) -> float:
    """Ajuste % sobre o TDEE, já escalado pelo ritmo (só onde o ritmo se aplica)."""
    base = GOAL_KCAL_ADJUSTMENT[goal]
    if goal in PACE_APPLIES:
        return base * PACE_MULTIPLIER[pace]
    return base


def weekly_rate_kg(tdee: float, goal: Goal, pace: GoalPace) -> float:
    """Ritmo de mudança de peso estimado (kg/semana, com sinal) pra esse objetivo
    e ritmo. Vem do déficit/superávit diário: (Δkcal/dia × 7) / 7700."""
    daily_delta = tdee * goal_adjustment_for(goal, pace)
    return round(daily_delta * 7 / KCAL_PER_KG_BODY, 3)


def compute_auto_goal(
    biological_sex: BiologicalSex,
    weight_kg: float,
    height_cm: float,
    age: int,
    activity_level: ActivityLevel,
    goal: Goal,
    pace: GoalPace = GoalPace.NORMAL,
) -> dict:
    bmr = calculate_bmr(biological_sex, weight_kg, height_cm, age)
    tdee = calculate_tdee(bmr, activity_level)
    target_kcal = tdee * (1 + goal_adjustment_for(goal, pace))

    protein_g = GOAL_PROTEIN_G_PER_KG[goal] * weight_kg
    fat_g = (target_kcal * FAT_KCAL_FRACTION) / KCAL_PER_G_FAT

    remaining_kcal = target_kcal - (protein_g * KCAL_PER_G_PROTEIN) - (fat_g * KCAL_PER_G_FAT)
    carbs_g = max(remaining_kcal, 0) / KCAL_PER_G_CARB

    return {
        "kcal": round(target_kcal),
        "protein_g": round(protein_g, 1),
        "carbs_g": round(carbs_g, 1),
        "fat_g": round(fat_g, 1),
    }
