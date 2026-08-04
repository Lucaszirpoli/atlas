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
- "sem_ovo", "sem_frutos_do_mar" — as outras restrições da lista do questionário

Além dessas, cada valor de `questionnaire.FOOD_DISLIKES` ("whey", "ovo",
"brocolis", "banana"...) também é um token válido aqui. Era exatamente esse o
buraco: a pessoa marcava "não como whey protein" e o gerador servia whey, porque
só as 4 restrições acima chegavam até aqui. Agora o vocabulário é o mesmo em
todo o caminho — questionário -> perfil -> motor.

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
SEM_OVO = "sem_ovo"
SEM_FRUTOS_DO_MAR = "sem_frutos_do_mar"

ALL_RESTRICTIONS = (
    VEGANO, VEGETARIANO, SEM_LACTOSE, SEM_GLUTEN, SEM_OVO, SEM_FRUTOS_DO_MAR,
)


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
    FoodRole("whey protein", "protein", frozenset({VEGANO, SEM_LACTOSE, "whey"}), (CAFE, LANCHE)),
    FoodRole("Proteína isolada de ervilha", "protein", frozenset(), (CAFE, LANCHE)),
]

# Proteínas "de verdade" (comida no prato), sem o reforço em pó.
WHOLE_PROTEINS: list[FoodRole] = [
    FoodRole("frango peito grelhado", "protein", frozenset({VEGANO, VEGETARIANO}), (ALMOCO, JANTAR)),
    FoodRole("tilápia grelhada", "protein", frozenset({VEGANO, VEGETARIANO, "peixe"}), (ALMOCO, JANTAR)),
    FoodRole("carne bovina patinho grelhado", "protein", frozenset({VEGANO, VEGETARIANO}), (ALMOCO, JANTAR)),
    FoodRole("ovo de galinha cozido", "protein", frozenset({VEGANO, SEM_OVO, "ovo"}), (CAFE, JANTAR)),
    FoodRole("Tofu firme", "protein", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("Grão-de-bico cozido", "protein", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("Lentilha cozida", "protein", frozenset(), (ALMOCO, JANTAR)),
]

# Carbos do café da manhã vs. os do almoço/jantar (pra distribuir bem no dia).
BREAKFAST_CARBS: list[FoodRole] = [
    FoodRole("aveia em flocos", "carb", frozenset({SEM_GLUTEN, "aveia"}), (CAFE, LANCHE)),
    FoodRole("pão de forma integral", "carb", frozenset({SEM_GLUTEN}), (CAFE,)),
]
# Todos sem glúten (arroz, tubérculos, macarrão de arroz) — garantem capacidade
# de carboidrato mesmo pra quem não come trigo/aveia.
MAIN_CARBS: list[FoodRole] = [
    FoodRole("arroz branco cozido", "carb", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("batata doce cozida", "carb", frozenset({"batata_doce"}), (ALMOCO, JANTAR)),
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
    FoodRole("brócolis cozido", "veg", frozenset({"brocolis"}), (ALMOCO, JANTAR)),
    FoodRole("cenoura cozida", "veg", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("alface crespa crua", "veg", frozenset(), (ALMOCO, JANTAR)),
    FoodRole("tomate cru", "veg", frozenset({"tomate"}), (ALMOCO, JANTAR)),
]

# --- Frutas (porção fixa) --------------------------------------------------
FRUITS: list[FoodRole] = [
    FoodRole("banana prata", "fruit", frozenset({"banana"}), (CAFE, LANCHE)),
    FoodRole("maçã fuji", "fruit", frozenset(), (CAFE, LANCHE)),
    FoodRole("mamão papaya", "fruit", frozenset({"mamao"}), (CAFE, LANCHE)),
]

# --- Laticínios / bebida (porção fixa) -------------------------------------
DAIRY: list[FoodRole] = [
    FoodRole("leite integral", "dairy", frozenset({VEGANO, SEM_LACTOSE, "leite"}), (CAFE, LANCHE)),
    FoodRole("iogurte natural", "dairy", frozenset({VEGANO, SEM_LACTOSE}), (CAFE, LANCHE)),
    FoodRole("queijo minas frescal", "dairy", frozenset({VEGANO, SEM_LACTOSE, "queijo_forte"}), (CAFE,)),
    FoodRole("Leite de soja (sem açúcar)", "dairy", frozenset(), (CAFE, LANCHE)),
    FoodRole("Iogurte de soja", "dairy", frozenset(), (CAFE, LANCHE)),
]


def pick_allowed(roles: list[FoodRole], restrictions: frozenset[str], index: int = 0) -> FoodRole | None:
    """Primeira role permitida a partir de `index` (rotativo p/ variedade)."""
    allowed = [r for r in roles if r.allowed(restrictions)]
    if not allowed:
        return None
    return allowed[index % len(allowed)]


# Tokens que EXCLUEM algum alimento do catálogo.
CATALOG_TOKENS: frozenset[str] = frozenset(
    tok
    for grupo in (
        PROTEIN_BOOSTERS, WHOLE_PROTEINS, BREAKFAST_CARBS, MAIN_CARBS,
        FATS, VEGGIES, FRUITS, DAIRY,
    )
    for role in grupo
    for tok in role.excluded_by
)

# Tokens que o motor honra SEM precisar excluir nada: o alimento simplesmente
# não existe no catálogo curado (não há frutos do mar, fígado, jiló, cogumelo…),
# então quem marcou isso já está atendido. Listados pra não virarem "não sei
# filtrar" numa mensagem de aviso que só assustaria à toa.
TRIVIAL_TOKENS: frozenset[str] = frozenset({
    SEM_FRUTOS_DO_MAR, "frutos_do_mar", "figado", "jilo", "cogumelo", "cebola",
    "pimentao", "beterraba", "abobrinha", "tapioca",
})

# O que o motor NÃO resolve sozinho: halal/kosher dependem da procedência da
# carne (não dá pra afirmar pela tabela) e low_carb é decisão de MACRO, não de
# alimento — muda a meta, não o cardápio. Quem pede isso merece ser avisado.
UNSUPPORTED_TOKENS: frozenset[str] = frozenset({"halal", "kosher", "low_carb"})

KNOWN_TOKENS: frozenset[str] = CATALOG_TOKENS | TRIVIAL_TOKENS

# Como a pessoa (ou o modelo, no chat) costuma escrever -> token canônico. O
# questionário já manda o token certo; isto existe pro texto livre do chat.
_SINONIMOS: dict[str, str] = {
    "sem lactose": SEM_LACTOSE, "lactose": SEM_LACTOSE, "intolerante a lactose": SEM_LACTOSE,
    "sem gluten": SEM_GLUTEN, "gluten": SEM_GLUTEN, "celiaco": SEM_GLUTEN,
    "sem ovo": SEM_OVO, "ovos": "ovo",
    "sem frutos do mar": SEM_FRUTOS_DO_MAR,
    "vegana": VEGANO, "vegetariana": VEGETARIANO,
    "sem whey": "whey", "whey protein": "whey", "sem suplemento": "whey",
    "sem leite": "leite", "sem peixe": "peixe", "sem banana": "banana",
    "sem brocolis": "brocolis", "sem tomate": "tomate", "sem aveia": "aveia",
    "sem batata doce": "batata_doce", "batata-doce": "batata_doce",
    "mamao": "mamao", "queijo": "queijo_forte",
}


def _canon(bruto) -> str:
    from app.core.text import normalize_search_text

    chave = normalize_search_text(str(bruto)).strip()
    if not chave:
        return ""
    sublinhado = chave.replace(" ", "_")
    if sublinhado in KNOWN_TOKENS or sublinhado in UNSUPPORTED_TOKENS:
        return sublinhado
    return _SINONIMOS.get(chave, sublinhado)


def normalize_tokens(valores) -> list[str]:
    """Texto solto -> tokens canônicos que o motor sabe aplicar. O que ele não
    sabe filtrar é DESCARTADO de propósito: melhor não filtrar do que fingir que
    filtrou. Quem chama avisa a pessoa (ver `unsupported`)."""
    saida: list[str] = []
    for bruto in valores or []:
        token = _canon(bruto)
        if token in KNOWN_TOKENS and token not in saida:
            saida.append(token)
    return saida


def unsupported(valores) -> list[str]:
    """Os pedidos que o motor NÃO resolve sozinho (halal, kosher, low carb, ou
    um alimento que não está no catálogo nem nos sinônimos). Serve pro app ser
    honesto em vez de entregar um cardápio que finge respeitar tudo."""
    fora: list[str] = []
    for bruto in valores or []:
        token = _canon(bruto)
        if token and token not in KNOWN_TOKENS and str(bruto) not in fora:
            fora.append(str(bruto))
    return fora
