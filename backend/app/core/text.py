"""Utilidades de texto para busca. Normalização sem acento/maiúsculas para
que "pao" case com "Pão", "acai" com "Açaí" etc. — o valor normalizado é
guardado na coluna `foods.search_text` (portável entre SQLite e Postgres,
sem depender da extensão unaccent)."""

import unicodedata


def normalize_search_text(*parts: str | None) -> str:
    """Junta as partes (nome, marca), remove acentos e baixa pra minúsculas.
    Ex.: ("Pão de Fôrma", "Pullman") -> "pao de forma pullman"."""
    raw = " ".join(p for p in parts if p)
    nfkd = unicodedata.normalize("NFKD", raw)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(ascii_only.lower().split())
