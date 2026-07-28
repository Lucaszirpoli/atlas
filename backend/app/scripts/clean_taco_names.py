"""Limpa os nomes do TACO que vieram no formato bruto da tabela oficial
("Arroz, integral, cozido") pro mesmo estilo natural do resto da base
("Arroz integral cozido").

Por que existe: o seed_taco_official.py importou a tabela oficial preservando
a formatação de coluna dela (Alimento, descritor 1, descritor 2, ..., preparo),
enquanto o seed_taco.py (mais antigo) usa nomes corridos. As DUAS convenções
coexistindo é o que o usuário via como "alimento mal feito" na busca — nomes
com vírgula lendo estranho, e às vezes o MESMO alimento aparecendo duas vezes
(uma vez em cada estilo) porque a formatação diferente escondia que eram o
mesmo prato.

A transformação é só remover as vírgulas (mantendo a ordem das palavras) — o
formato bruto da TACO já lista os descritores na ordem certa pra ler em
português, só com pontuação de tabela em vez de frase. Sem isso, "cru" x
"cozido" continua claro (a palavra final não muda), só o jeito de escrever.

Quando a limpeza faz dois alimentos ficarem com o MESMO nome (era o mesmo
prato nas duas convenções), NÃO apagamos nenhuma linha — apagar quebraria
o histórico de quem já registrou aquele food_id (regra 4, append-only). A
busca (food_service.search_local) já deduplica por nome exibido e mostra só
um. As duas linhas continuam existindo pro histórico de quem já usou a antiga.

Idempotente: só mexe em nome que ainda tem vírgula.

Uso: python -m app.scripts.clean_taco_names
"""

from __future__ import annotations

import re

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.food import Food, FoodSource

_VIRGULA = re.compile(r"\s*,\s*")
_ESPACOS = re.compile(r"\s+")


def _limpar(nome: str) -> str:
    sem_virgula = _VIRGULA.sub(" ", nome)
    return _ESPACOS.sub(" ", sem_virgula).strip()


def run() -> None:
    db = SessionLocal()
    try:
        alimentos = list(
            db.execute(
                select(Food).where(Food.source == FoodSource.TACO, Food.name.like("%,%"))
            ).scalars()
        )
        alterados = 0
        for f in alimentos:
            novo = _limpar(f.name)
            if novo != f.name:
                f.name = novo
                alterados += 1
        db.commit()
        print(f"Nomes do TACO limpos (sem vírgula de tabela): {alterados} de {len(alimentos)} candidatos.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
