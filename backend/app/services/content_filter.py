"""Filtro básico de conteúdo (+18) para nomes digitados pelo usuário.

Aplica-se ao cadastro MANUAL de alimento — a base de alimentos é compartilhada
entre todos os usuários, então um nome impróprio digitado por uma pessoa
apareceria na busca de todo mundo. Nomes vindos do Open Food Facts (código de
barras) são de produtos reais e não passam por aqui.

É um guarda simples e conservador: casa por PALAVRA inteira (após remover
acentos e baixar pra minúsculas), então "assado" não dispara por conter "ass".
A lista foca em termos claramente ofensivos/adultos que NÃO são palavras comuns
de comida — de propósito evita termos ambíguos (ex.: "coco", "cacete", "pinto",
"veado", "punheta") que também nomeiam alimentos reais no Brasil/Portugal. É
fácil de estender: basta adicionar o termo (sem acento, minúsculo) ao conjunto.
"""

import re
import unicodedata

# Termos bloqueados (normalizados: minúsculos e sem acento). Casados por palavra
# inteira. Mantido conservador pra não bloquear nomes legítimos de comida.
_BANNED: set[str] = {
    # PT-BR — palavrões / sexual explícito
    "caralho", "caralhos", "porra", "porras", "buceta", "bucetas", "boceta",
    "xoxota", "xereca", "piroca", "pirocas", "rola", "pica", "piru",
    "foder", "fodido", "fodida", "foda", "fodase", "fodendo",
    "puta", "putas", "putaria", "putinha", "vagabunda", "vadia", "vadias",
    "cuzao", "cuzudo", "arrombado", "arrombada", "corno", "cornos",
    "escroto", "escrota", "fdp", "pqp", "filhadaputa", "filhodaputa",
    "merda", "bosta", "boquete", "boquetes", "siririca", "punheteiro",
    "tesao", "gozada", "viado", "viadinho", "bicha", "sapatao",
    "pornografia", "porno", "porno",
    # EN — offensive / adult
    "fuck", "fucking", "fucker", "shit", "bitch", "dick", "pussy", "cunt",
    "penis", "vagina", "boobs", "tits", "whore", "slut", "porn", "porno",
    "xxx", "cum", "sex", "sexo", "nigger", "faggot", "asshole",
}


def _normalize(text: str) -> str:
    """Baixa pra minúsculas e remove acentos (café -> cafe)."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def contains_banned_term(text: str) -> bool:
    """True se o texto contém, como palavra inteira, algum termo bloqueado."""
    tokens = set(_TOKEN_RE.findall(_normalize(text)))
    return bool(tokens & _BANNED)
