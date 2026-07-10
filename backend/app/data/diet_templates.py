"""Dietas semi-prontas CURADAS (sem IA) — moldes de um dia inteiro de refeições
que o app ESCALA pra bater com a meta calórica da pessoa (calculada do objetivo
+ peso + altura). Não é prescrição médica; é um ponto de partida editável.

Cada item referencia um alimento REAL da base por uma busca (`q`) que resolve
pro alimento canônico da TACO (verificado), com uma grama-base (`g`). O total
de calorias do molde é só uma referência: na hora de usar, todas as gramas são
multiplicadas por (meta_da_pessoa / total_do_molde), então a mesma dieta serve
pra quem precisa de 1600 ou 3000 kcal — só muda a porção.

`goals` diz para quais objetivos a dieta combina mais (só rótulo — todas podem
ser escolhidas por qualquer pessoa). Nomes de refeição batem com
DEFAULT_MEAL_CATEGORY_NAMES.
"""

from __future__ import annotations

# Objetivos (batem com o enum Goal): emagrecimento, hipertrofia, manutencao,
# performance, recomposicao.

DIET_TEMPLATES: list[dict] = [
    {
        "id": "classica",
        "name": "Clássica equilibrada",
        "tagline": "Arroz, feijão, frango, ovo e fruta",
        "description": (
            "O prato brasileiro de sempre, balanceado entre carboidrato, proteína e "
            "gordura boa. Combina com quase todo objetivo — a porção é ajustada pra sua meta."
        ),
        "goals": ["manutencao", "emagrecimento", "recomposicao", "performance"],
        "meals": [
            {"category": "Café da manhã", "items": [
                {"q": "pão francês", "g": 50},
                {"q": "ovo de galinha cozido", "g": 100},
                {"q": "banana prata", "g": 100},
                {"q": "leite integral", "g": 200},
            ]},
            {"category": "Almoço", "items": [
                {"q": "arroz branco cozido", "g": 150},
                {"q": "feijão carioca cozido", "g": 120},
                {"q": "frango peito grelhado", "g": 130},
                {"q": "alface crespa crua", "g": 40},
                {"q": "tomate cru", "g": 50},
                {"q": "azeite de oliva", "g": 5},
            ]},
            {"category": "Lanche da tarde", "items": [
                {"q": "iogurte natural", "g": 170},
                {"q": "aveia em flocos", "g": 30},
                {"q": "maçã fuji", "g": 130},
            ]},
            {"category": "Jantar", "items": [
                {"q": "batata doce cozida", "g": 150},
                {"q": "frango peito grelhado", "g": 120},
                {"q": "brócolis cozido", "g": 80},
            ]},
        ],
    },
    {
        "id": "lowcarb",
        "name": "Low carb",
        "tagline": "Menos carboidrato, mais proteína e gordura boa",
        "description": (
            "Reduz arroz/pão e reforça proteína, ovos, queijo, abacate e legumes. "
            "Muitas pessoas acham mais fácil controlar a fome assim durante um emagrecimento."
        ),
        "goals": ["emagrecimento", "recomposicao"],
        "meals": [
            {"category": "Café da manhã", "items": [
                {"q": "ovo de galinha cozido", "g": 150},
                {"q": "queijo minas frescal", "g": 40},
                {"q": "abacate", "g": 80},
            ]},
            {"category": "Almoço", "items": [
                {"q": "frango peito grelhado", "g": 150},
                {"q": "alface crespa crua", "g": 50},
                {"q": "tomate cru", "g": 60},
                {"q": "cenoura cozida", "g": 60},
                {"q": "azeite de oliva", "g": 10},
            ]},
            {"category": "Lanche da tarde", "items": [
                {"q": "iogurte natural", "g": 170},
                {"q": "whey protein", "g": 20},
            ]},
            {"category": "Jantar", "items": [
                {"q": "carne bovina patinho grelhado", "g": 150},
                {"q": "brócolis cozido", "g": 100},
                {"q": "azeite de oliva", "g": 8},
            ]},
        ],
    },
    {
        "id": "hipertrofia",
        "name": "Alta proteína (ganho)",
        "tagline": "Mais calorias e proteína pra construir músculo",
        "description": (
            "Volume maior de comida e proteína bem distribuída no dia, com carboidrato "
            "pra treinar forte. Feita pra quem quer ganhar massa — a porção acompanha sua meta."
        ),
        "goals": ["hipertrofia", "performance"],
        "meals": [
            {"category": "Café da manhã", "items": [
                {"q": "aveia em flocos", "g": 60},
                {"q": "leite integral", "g": 250},
                {"q": "banana prata", "g": 120},
                {"q": "ovo de galinha cozido", "g": 100},
            ]},
            {"category": "Almoço", "items": [
                {"q": "arroz branco cozido", "g": 200},
                {"q": "feijão carioca cozido", "g": 120},
                {"q": "frango peito grelhado", "g": 180},
                {"q": "azeite de oliva", "g": 8},
            ]},
            {"category": "Lanche da tarde", "items": [
                {"q": "whey protein", "g": 30},
                {"q": "pão de forma integral", "g": 50},
                {"q": "banana prata", "g": 100},
            ]},
            {"category": "Jantar", "items": [
                {"q": "arroz integral cozido", "g": 150},
                {"q": "carne bovina patinho grelhado", "g": 150},
                {"q": "brócolis cozido", "g": 80},
            ]},
            {"category": "Ceia", "items": [
                {"q": "iogurte natural", "g": 170},
                {"q": "aveia em flocos", "g": 30},
            ]},
        ],
    },
    {
        "id": "vegetariana",
        "name": "Vegetariana equilibrada",
        "tagline": "Sem carne — ovo, leite, leguminosas e legumes",
        "description": (
            "Proteína vinda de ovos, laticínios e leguminosas (feijão), com bastante "
            "vegetal. Equilibrada e completa para quem não come carne."
        ),
        "goals": ["manutencao", "emagrecimento", "recomposicao"],
        "meals": [
            {"category": "Café da manhã", "items": [
                {"q": "aveia em flocos", "g": 50},
                {"q": "leite integral", "g": 200},
                {"q": "maçã fuji", "g": 130},
                {"q": "ovo de galinha cozido", "g": 100},
            ]},
            {"category": "Almoço", "items": [
                {"q": "arroz integral cozido", "g": 150},
                {"q": "feijão preto cozido", "g": 140},
                {"q": "ovo de galinha cozido", "g": 100},
                {"q": "queijo minas frescal", "g": 40},
                {"q": "alface crespa crua", "g": 40},
                {"q": "tomate cru", "g": 50},
                {"q": "azeite de oliva", "g": 8},
            ]},
            {"category": "Lanche da tarde", "items": [
                {"q": "iogurte natural", "g": 170},
                {"q": "banana prata", "g": 100},
                {"q": "aveia em flocos", "g": 20},
            ]},
            {"category": "Jantar", "items": [
                {"q": "batata doce cozida", "g": 150},
                {"q": "ovo de galinha cozido", "g": 100},
                {"q": "brócolis cozido", "g": 100},
                {"q": "azeite de oliva", "g": 6},
            ]},
        ],
    },
    {
        "id": "economica",
        "name": "Econômica do dia a dia",
        "tagline": "Barata e prática: arroz, feijão, ovo e fruta",
        "description": (
            "Só com o que costuma ter em casa e cabe no bolso — arroz, feijão, ovo, pão "
            "e banana. Prova que dá pra comer bem sem gastar muito."
        ),
        "goals": ["manutencao", "emagrecimento", "performance"],
        "meals": [
            {"category": "Café da manhã", "items": [
                {"q": "pão francês", "g": 100},
                {"q": "ovo de galinha cozido", "g": 100},
                {"q": "banana prata", "g": 100},
            ]},
            {"category": "Almoço", "items": [
                {"q": "arroz branco cozido", "g": 180},
                {"q": "feijão carioca cozido", "g": 150},
                {"q": "ovo de galinha cozido", "g": 100},
                {"q": "tomate cru", "g": 50},
            ]},
            {"category": "Lanche da tarde", "items": [
                {"q": "banana prata", "g": 120},
                {"q": "aveia em flocos", "g": 40},
                {"q": "leite integral", "g": 200},
            ]},
            {"category": "Jantar", "items": [
                {"q": "arroz branco cozido", "g": 150},
                {"q": "feijão carioca cozido", "g": 120},
                {"q": "ovo de galinha cozido", "g": 100},
            ]},
        ],
    },
    {
        "id": "leve",
        "name": "Leve e colorida",
        "tagline": "Peixe, legumes e frutas — bem digestível",
        "description": (
            "Baseada em peixe, muito vegetal, fruta e azeite (estilo mediterrâneo). "
            "Leve, colorida e rica em proteína magra."
        ),
        "goals": ["emagrecimento", "recomposicao", "manutencao"],
        "meals": [
            {"category": "Café da manhã", "items": [
                {"q": "iogurte natural", "g": 170},
                {"q": "aveia em flocos", "g": 40},
                {"q": "mamão papaya", "g": 150},
            ]},
            {"category": "Almoço", "items": [
                {"q": "arroz integral cozido", "g": 130},
                {"q": "tilápia grelhada", "g": 150},
                {"q": "brócolis cozido", "g": 80},
                {"q": "cenoura cozida", "g": 60},
                {"q": "azeite de oliva", "g": 8},
            ]},
            {"category": "Lanche da tarde", "items": [
                {"q": "maçã fuji", "g": 130},
                {"q": "whey protein", "g": 20},
            ]},
            {"category": "Jantar", "items": [
                {"q": "batata doce cozida", "g": 130},
                {"q": "tilápia grelhada", "g": 130},
                {"q": "alface crespa crua", "g": 40},
                {"q": "tomate cru", "g": 50},
                {"q": "azeite de oliva", "g": 6},
            ]},
        ],
    },
]


def get_template(template_id: str) -> dict | None:
    return next((t for t in DIET_TEMPLATES if t["id"] == template_id), None)
