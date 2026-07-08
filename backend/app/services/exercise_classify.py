"""Classifica um exercício como COMPOSTO (multiarticular, vários grupos) ou
ISOLADO (monoarticular, um grupo) — base da regra de proporção intra-sessão
dos métodos (ex: Kuba 40% composto / 60% isolado).

Heurística por nome (nomes em PT-BR da nossa biblioteca) com fallback pela
contagem de grupos secundários. Nome vem primeiro porque é mais confiável que
os metadados importados.
"""

from app.core.text import normalize_search_text

# Monoarticulares clássicos — se o nome bate, é isolado.
_ISOLATION_KEYWORDS = {
    "rosca", "curl", "extensao", "extensora", "flexora", "elevacao lateral",
    "elevacao frontal", "crucifixo", "voador", "fly", "peck deck", "pec deck",
    "panturrilha", "gemeos", "encolhimento", "shrug", "abdominal", "prancha",
    "aducao", "abducao", "kickback", "coice", "triceps testa", "triceps corda",
    "triceps frances", "pullover", "face pull", "reverse fly", "crossover",
    "extensao de perna", "flexao de perna", "elevacao de panturrilha",
}

# Multiarticulares clássicos — se o nome bate, é composto.
_COMPOUND_KEYWORDS = {
    "agachamento", "supino", "terra", "levantamento terra", "remada",
    "desenvolvimento", "puxada", "pulldown", "leg press", "avanco", "afundo",
    "passada", "barra fixa", "paralelas", "mergulho", "stiff", "hip thrust",
    "elevacao pelvica", "clean", "arranco", "arremesso", "good morning",
    "flexao de braco", "pull up", "chin up", "push up", "levantamento",
    "desenvolvimento militar", "bulgaro", "hack", "sumo",
}


def classify_is_compound(name: str, secondary_groups, equipment=None) -> bool:
    """True = composto, False = isolado."""
    norm = normalize_search_text(name)

    # 1) nome com palavra-chave de isolamento vence (evita "extensora" cair em
    #    composto por ter grupo secundário importado errado).
    for kw in _ISOLATION_KEYWORDS:
        if kw in norm:
            return False
    # 2) nome com palavra-chave de composto.
    for kw in _COMPOUND_KEYWORDS:
        if kw in norm:
            return True
    # 3) fallback: tem grupo secundário => provavelmente multiarticular.
    try:
        return len(secondary_groups or []) >= 1
    except TypeError:
        return False
