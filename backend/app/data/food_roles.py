"""Catálogo curado de alimentos por FUNÇÃO no prato (proteína, carbo, gordura,
vegetal, fruta, laticínio), usado pelo construtor determinístico de dieta
(app/ai/diet_engine.py).

Cada item referencia um alimento REAL da base por uma busca (`query`) já
verificada — as mesmas que as dietas semi-prontas usam, que resolvem pro
alimento canônico da TACO / seed vegano. Cada alimento carrega as restrições
que o EXCLUEM (`excluded_by`), o que garante que um plano vegano nunca receba
frango, um plano sem-lactose nunca receba leite comum, etc.

Tokens de restrição canônicos (o app manda esses no request):
- "vegano"       — sem nenhum produto animal
- "vegetariano"  — sem carne/peixe (ovo e laticínio ok)
- "sem_lactose"  — sem laticínio com lactose
- "sem_gluten"   — sem trigo/aveia com glúten

`meals` diz em quais refeições aquele alimento costuma cair (o motor distribui
as gramas por essas refeições). Nomes batem com DEFAULT_MEAL_CATEGORY_NAMES.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Refeições canônicas (batem com meal_service.DEFAULT_MEAL_CATEGORY_NAMES).
CAFE = "Café da manhã"
LANCHE_MANHA = "Lanche da manhã"
ALMOCO = "Almoço"
LANCHE = "Lanche da tarde"
JANTAR = "Jantar"
CEIA = "Ceia"

VEGANO = "vegano"
VEGETARIANO = "vegetariano"
SEM_LACTOSE = "sem_lactose"
SEM_GLUTEN = "sem_gluten"

ALL_RESTRICTIONS = (VEGANO, VEGETARIANO, SEM_LACTOSE, SEM_GLUTEN)


@dataclass(frozen=True)
class FoodRole:
    query: str                         # busca verificada que resolve na base
    macro: str                         # "protein"|"carb"|"fat"|"veg"|"fruit"|"dairy"
    excluded_by: frozenset[str] = field(default_factory=frozenset)
    meals: tuple[str, ...] = (ALMOCO, JANTAR)

    def allowed(self, restrictions: frozenset[str]) -> bool:
        return self.excluded_by.isdisjoint(restrictions)


# --- Proteínas -------------------------------------------------------------
# Proteína "REFORÇO": muito densa e pobre nos outros macros — é o que permite
# bater metas altas de proteína sem estourar caloria. Um destes entra sempre
# como solucionador, junto de uma proteína "de verdade" (comida) da lista acima.
PROTEIN_BOOSTERS: list[FoodRole] = [
    FoodRole("whey protein", "protein", frozenset({VEGANO, SEM_LACTOSE}), (CAFE, LANCHE)),
    FoodRole("Proteína isolada de ervilha", "protein", frozenset(), (CAFE, LANCHE)),
]

# Proteínas "de verdade" (comida no prato), sem o reforço em pó.
WHOLE_PROTEINS: list[FoodRole] = [
    FoodRole("frango peito grelhado", "protein", frozenset({VEGANO, VEGETARIANO}), (ALMOCO, JANTAR)),
    FoodRole("tilápia grelhada", "protein", frozenset({VEGANO, VEGETARIANO}), (ALMOCO, JANTAR)),
    FoodRole("carne bovina patinho grelhado", "protein", frozenset({VEGANO, VEGETARIANO}), (ALMOCO, JANTAR)),
    FoodRole("ovo de galinha cozido", "protein", frozenset({VEGANO}), (CAFE, JANTAR)),
    FoodRole("Tofu firme", "protein", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("Grão-de-bico cozido", "protein", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("Lentilha cozida", "protein", frozenset(), (ALMOCO, JANTAR)),
]

# Carbos do café da manhã vs. os do almoço/jantar (pra distribuir bem no dia).
BREAKFAST_CARBS: list[FoodRole] = [
    FoodRole("aveia em flocos", "carb", frozenset({SEM_GLUTEN}), (CAFE, LANCHE)),
    FoodRole("pão de forma integral", "carb", frozenset({SEM_GLUTEN}), (CAFE,)),
]
# Todos sem glúten (arroz, tubérculos, macarrão de arroz) — garantem capacidade
# de carboidrato mesmo pra quem não come trigo/aveia.
MAIN_CARBS: list[FoodRole] = [
    FoodRole("arroz branco cozido", "carb", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("batata doce cozida", "carb", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("macarrão de arroz", "carb", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("mandioca cozida", "carb", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("arroz integral cozido", "carb", frozenset(), (ALMOCO, JANTAR)),
]

# --- Gorduras --------------------------------------------------------------
FATS: list[FoodRole] = [
    FoodRole("azeite de oliva", "fat", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("abacate", "fat", frozenset(), (CAFE, LANCHE)),
    FoodRole("Pasta de amendoim integral", "fat", frozenset(), (CAFE, LANCHE)),
    FoodRole("Castanha de caju", "fat", frozenset(), (LANCHE,)),
]

# --- Vegetais (porção fixa; fibra/micronutriente) --------------------------
VEGGIES: list[FoodRole] = [
    FoodRole("brócolis cozido", "veg", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("cenoura cozida", "veg", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("alface crespa crua", "veg", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("tomate cru", "veg", frozenset(), (ALMOCO, JANTAR)),
]

# --- Frutas (porção fixa) --------------------------------------------------
FRUITS: list[FoodRole] = [
    FoodRole("banana prata", "fruit", frozenset(), (CAFE, LANCHE)),
    FoodRole("maçã fuji", "fruit", frozenset(), (CAFE, LANCHE)),
    FoodRole("mamão papaya", "fruit", frozenset(), (CAFE, LANCHE)),
]

# --- Laticínios / bebida (porção fixa) -------------------------------------
DAIRY: list[FoodRole] = [
    FoodRole("leite integral", "dairy", frozenset({VEGANO, SEM_LACTOSE}), (CAFE, LANCHE)),
    FoodRole("iogurte natural", "dairy", frozenset({VEGANO, SEM_LACTOSE}), (CAFE, LANCHE)),
    FoodRole("queijo minas frescal", "dairy", frozenset({VEGANO, SEM_LACTOSE}), (CAFE,)),
    FoodRole("Leite de soja (sem açúcar)", "dairy", frozenset(), (CAFE, LANCHE)),
    FoodRole("Iogurte de soja", "dairy", frozenset(), (CAFE, LANCHE)),
]


def pick_allowed(roles: list[FoodRole], restrictions: frozenset[str], index: int = 0) -> FoodRole | None:
    """Primeira role permitida a partir de `index` (rotativo p/ variedade)."""
    allowed = [r for r in roles if r.allowed(restrictions)]
    if not allowed:
        return None
    return allowed[index % len(allowed)]
