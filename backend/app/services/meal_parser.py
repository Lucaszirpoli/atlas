"""Parser determinístico de refeição em linguagem natural — SEM IA, sem custo
de token. Transforma um texto tipo "30g de requeijão, 2 ovos e um pão francês"
numa lista de itens (quantidade em gramas + alimento da base), pronta pra
pessoa revisar e registrar.

A ideia: registrar comida é essencialmente extrair (quantidade + unidade +
nome do alimento) e casar com a base — coisa que regra + dicionário fazem de
forma confiável, instantânea e offline, melhor que um LLM pra essa tarefa
(não alucina, não custa). O usuário sempre revisa antes de salvar, então uma
estimativa razoável já resolve; ele ajusta a grama se quiser.
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.food import Food
from app.services import food_service


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Números por extenso (chave sem acento/minúscula).
_NUMBER_WORDS: dict[str, float] = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
    "meia": 0.5, "meio": 0.5, "duzia": 12, "meia-duzia": 6,
}

# Unidades -> ("g"|"ml"|"portion", fator pra grama/ml quando aplicável).
_UNIT_GRAMS = {"g", "grama", "gramas", "gr", "grs"}
_UNIT_KG = {"kg", "quilo", "quilos", "quilograma", "quilogramas", "kgs"}
_UNIT_ML = {"ml", "mililitro", "mililitros"}
_UNIT_L = {"l", "litro", "litros", "lt"}
# Unidades de "porção" — sem grama fixa; usa o default_portion_g do alimento.
_UNIT_PORTION = {
    "unidade", "unidades", "un", "und", "fatia", "fatias", "colher", "colheres",
    "colherada", "colheradas", "xicara", "xicaras", "copo", "copos", "concha",
    "conchas", "pedaco", "pedacos", "posta", "postas", "file", "files", "porcao",
    "porcoes", "pote", "potes", "bola", "bolas", "scoop", "dose", "doses",
}
_ALL_UNITS = _UNIT_GRAMS | _UNIT_KG | _UNIT_ML | _UNIT_L | _UNIT_PORTION

# Palavras de ligação a ignorar no nome do alimento.
_FILLER = {"de", "do", "da", "dos", "das", "com", "sem", "uns", "umas", "e", "no", "na", "ao", "a", "o"}

_SPLIT_RE = re.compile(r"\s*(?:,|;|\+|\be\b|\n|\.)\s*")


def _parse_segment(db: Session, segment: str) -> dict | None:
    seg = segment.strip()
    if not seg:
        return None
    tokens = seg.split()
    norm_tokens = [_strip_accents(t).lower() for t in tokens]

    # Pula palavras de ligação no COMEÇO ("no duas pizzas" -> "duas pizzas") pra
    # não estragar a leitura da quantidade (que olha só o 1º token) quando sobra
    # um filler antes do número.
    while len(norm_tokens) > 1 and norm_tokens[0] in _FILLER:
        tokens = tokens[1:]
        norm_tokens = norm_tokens[1:]

    quantity: float | None = None
    unit: str | None = None
    consumed = 0  # quantos tokens do início já viraram quantidade/unidade

    # 1) quantidade: número (3, 2.5, 2,5) ou por extenso (dois, meia)
    first = norm_tokens[0] if norm_tokens else ""
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)", first)
    if m:
        quantity = float(m.group(1).replace(",", "."))
        consumed = 1
    elif first in _NUMBER_WORDS:
        quantity = _NUMBER_WORDS[first]
        consumed = 1
    else:
        # número grudado na unidade: "30g", "150ml"
        m2 = re.fullmatch(r"(\d+(?:[.,]\d+)?)([a-zç]+)", first)
        if m2 and _strip_accents(m2.group(2)) in _ALL_UNITS:
            quantity = float(m2.group(1).replace(",", "."))
            unit = _strip_accents(m2.group(2))
            consumed = 1

    # 2) unidade logo após o número (se ainda não peguei grudada)
    if unit is None and consumed < len(norm_tokens):
        cand = norm_tokens[consumed]
        if cand in _ALL_UNITS:
            unit = cand
            consumed += 1
            # "colher de sopa", "copo de leite" — pula preposição, mas o resto
            # é o alimento; não consumimos além da unidade.

    # 3) nome do alimento = resto, sem palavras de ligação
    rest_tokens = [tok for tok, nt in zip(tokens[consumed:], norm_tokens[consumed:]) if nt not in _FILLER]
    food_query = " ".join(rest_tokens).strip()

    if not food_query:
        return {
            "raw": seg,
            "query": "",
            "food": None,
            "alternatives": [],
            "quantity_g": None,
            "quantity": quantity,
            "unit": unit,
            "status": "sem_alimento",  # ex: pessoa disse só "30g"
        }

    matches = food_service.search_local(db, food_query, limit=6)
    # Sem match local (ex: uma MARCA como "danone", "nescau"), tenta o Open
    # Food Facts ao vivo — ele cacheia o que achar, então na próxima já sai do
    # banco local. Falhou a rede? segue sem match (a pessoa corrige na revisão).
    if not matches:
        try:
            matches = food_service.search_brands_live(db, food_query, limit=6)
        except Exception:
            matches = []
    food = matches[0] if matches else None

    quantity_g, status = _to_grams(quantity, unit, food)

    return {
        "raw": seg,
        "query": food_query,
        "food": food,
        "alternatives": matches[1:5],
        "quantity_g": quantity_g,
        "quantity": quantity,
        "unit": unit,
        "status": status if food else "nao_encontrado",
    }


def _to_grams(quantity: float | None, unit: str | None, food: Food | None) -> tuple[float | None, str]:
    q = quantity if quantity is not None else 1.0
    if unit in _UNIT_GRAMS:
        return round(q, 1), "ok"
    if unit in _UNIT_KG:
        return round(q * 1000, 1), "ok"
    if unit in _UNIT_ML:
        return round(q, 1), "ok"  # densidade ~1 g/ml (aproximação pra registro)
    if unit in _UNIT_L:
        return round(q * 1000, 1), "ok"
    # porção ou sem unidade: usa a porção padrão do alimento
    if food is not None:
        portion = food.default_portion_g or 100.0
        return round(q * portion, 1), "porcao_estimada"
    # sem alimento casado e sem unidade de peso: não dá pra estimar
    if unit is None:
        return None, "porcao_estimada"
    return None, "ok"


def parse_meal_text(db: Session, text: str) -> list[dict]:
    """Quebra o texto em itens e resolve cada um. Sempre retorna algo revisável
    (mesmo itens que não casaram, pra pessoa corrigir)."""
    if not text or not text.strip():
        return []
    segments = [s for s in _SPLIT_RE.split(text.strip()) if s and s.strip()]
    out: list[dict] = []
    for seg in segments:
        parsed = _parse_segment(db, seg)
        if parsed is not None:
            out.append(parsed)
    return out
