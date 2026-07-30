"""Limpeza da base de alimentos: esconde homônimo sem marca e duplicata de ruído.

O problema que este script resolve, no relato do usuário: pesquisar "pipoca" ou
"cuscuz" no app trazia vários resultados SEM MARCA, com calorias bem diferentes
e nada no nome explicando a diferença — "um vai ter mais calorias que o outro,
sendo que não tem nada especificando, não dá pra saber se um é cru, um é
cozido". A regra do produto que ele definiu:

  - homônimos COM MARCA diferente podem coexistir (pipoca A, pipoca B, pipoca C,
    cada uma com sua marca visível);
  - homônimos SEM marca, não: fica UM só, ou o nome precisa dizer o que
    diferencia (cru, cozido, com pele...).

De onde vinham: `search_brands_live` gravava TODO resultado do Open Food Facts
como alimento permanente, inclusive os que vêm sem o campo de marca preenchido.
A causa foi corrigida em `food_service`/`open_food_facts` (produto sem marca não
é mais gravado, e a marca escondida no nome — "Cuzcuz - Gostozin" — passou a ser
extraída). Este script limpa o que já entrou.

ESCONDE, NUNCA APAGA (`hidden=True`): `meal_log_items` referencia `food_id` por
FK, então apagar quebraria o histórico de quem já registrou aquele alimento —
e o histórico é append-only (regra 4 do projeto). Escondido sai da busca e
continua abrindo no diário. O código de barras também continua achando
(`get_by_barcode` não filtra `hidden`), então escanear o produto na mão funciona.

Idempotente: roda em todo boot.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.food import Food, FoodSource


def _norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


# Qualificadores que NÃO mudam o alimento pra quem registra o que comeu: só
# dizem se tem sal. Dois alimentos que diferem apenas nisto são a mesma comida.
_RUIDO = (
    "com sal", "sem sal", "com adicao de sal", "sem adicao de sal",
    "salgado", "salgada",
)

# Marcadores de PREPARO ou de PARTE do alimento. Dois alimentos que diferem
# nestes NÃO são duplicata — são comidas diferentes (arroz cru tem quase 3x as
# calorias do cozido), e é justamente esta informação que o usuário quer ver.
_DISTINTIVOS = (
    "cru", "crua", "cozido", "cozida", "assado", "assada", "frito", "frita",
    "grelhado", "grelhada", "refogado", "refogada", "ensopado", "em conserva",
    "desidratado", "desidratada", "torrado", "torrada", "defumado", "defumada",
    "integral", "desnatado", "semidesnatado", "light", "diet", "zero", "em po",
    "com pele", "sem pele", "com casca", "sem casca", "com osso", "sem osso",
)


def _base(nome: str) -> str:
    """Nome sem os qualificadores de ruído — a chave de "é a mesma comida"."""
    n = _norm(nome)
    for r in _RUIDO:
        n = n.replace(r, " ")
    return re.sub(r"\s+", " ", n).strip()


def _base_nua(nome: str) -> str:
    """Nome sem ruído E sem distintivos — a chave de "é o mesmo ALIMENTO,
    preparado ou cortado de formas diferentes".

    Precisa ser separada de `_base` porque as duas perguntas são diferentes:
    `_base` agrupa "cuscuz cozido" com "cuscuz cozido com sal" (duplicata);
    `_base_nua` agrupa "frango sobrecoxa assada" com "frango sobrecoxa com pele
    assada" e "sem pele assada" — que NÃO são duplicatas, mas revelam que a
    primeira é ambígua. Sem esta função a regra 3 nunca disparava, porque os três
    nomes tinham `_base` diferente e caíam em grupos separados.
    """
    n = _base(nome)
    for d in _DISTINTIVOS:
        n = re.sub(rf"\b{d}\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _distintivos(nome: str) -> frozenset[str]:
    n = _norm(nome)
    return frozenset(d for d in _DISTINTIVOS if re.search(rf"\b{d}\b", n))


def _sem_marca(f: Food) -> bool:
    return not (f.brand or "").strip()


def _qualidade(f: Food) -> tuple:
    """Quem GANHA quando há empate (menor = melhor).

    TACO na frente do Open Food Facts: é tabela oficial brasileira, com nome
    descritivo e valor conferido, contra dado de rótulo digitado por voluntário.
    Depois o nome mais curto (o nome-base costuma ser o que a pessoa procura) e o
    id menor, pra a escolha ser estável entre execuções.
    """
    return (
        0 if f.source == FoodSource.TACO else 1,
        len(f.name or ""),
        f.id,
    )


def run() -> None:
    db = SessionLocal()
    try:
        # --- 0) Marca escondida DENTRO do nome --------------------------------
        # "Cuzcuz - Gostozin", "Creme de ricota light ervas finas - Godam": o OFF
        # deixou o campo de marca vazio e pôs a marca no nome. Enquanto ela fica
        # ali, o produto conta como "sem marca" e é indistinguível dos homônimos —
        # com a marca no lugar certo ele vira um produto legítimo, que PODE
        # coexistir com outros do mesmo nome. Por isso este passo vem antes de
        # qualquer regra de esconder: ele SALVA linhas em vez de escondê-las.
        # (Em ingestão nova isto já acontece na origem — open_food_facts.)
        from app.services.open_food_facts import _marca_no_nome

        recuperados = 0
        for f in db.execute(
            select(Food).where(Food.source == FoodSource.OPEN_FOOD_FACTS)
        ).scalars():
            if (f.brand or "").strip():
                continue
            nome, marca = _marca_no_nome((f.name or "").strip(), None)
            if marca:
                f.name, f.brand = nome, marca
                recuperados += 1
        if recuperados:
            db.flush()

        visiveis = list(
            db.execute(select(Food).where(Food.hidden.is_(False))).scalars()
        )
        escondidos: list[tuple[Food, str]] = []

        # --- 1) Homônimos SEM MARCA -------------------------------------------
        # Mesmo nome exato, nenhum dos dois com marca: fica um. (Com marca
        # diferente, os dois ficam — é a regra do produto.)
        por_nome: dict[str, list[Food]] = defaultdict(list)
        for f in visiveis:
            if _sem_marca(f):
                por_nome[_norm(f.name)].append(f)
        for nome, itens in por_nome.items():
            if len(itens) < 2:
                continue
            itens.sort(key=_qualidade)
            for perdedor in itens[1:]:
                escondidos.append((perdedor, f"homônimo sem marca de id={itens[0].id}"))

        ja_escondidos = {f.id for f, _ in escondidos}

        # --- 2) Duplicata de RUÍDO -------------------------------------------
        # Mesma comida, mesmo preparo, diferindo só em "com sal"/"salgado", e com
        # calorias praticamente iguais. Só vale quando um dos nomes NÃO tem o
        # qualificador: aí existe um nome-base limpo pra ficar. Quando os dois
        # têm ("manteiga com sal" x "manteiga sem sal"), os dois ficam — é como
        # o produto é vendido e a pessoa escolhe de verdade.
        grupos: dict[tuple[str, frozenset[str]], list[Food]] = defaultdict(list)
        for f in visiveis:
            if f.id in ja_escondidos or not _sem_marca(f):
                continue
            grupos[(_base(f.name), _distintivos(f.name))].append(f)

        for (base, _), itens in grupos.items():
            if len(itens) < 2:
                continue
            kcals = [f.kcal_per_100g or 0 for f in itens]
            # 6% ou 6 kcal de folga: acima disso a diferença é comida diferente.
            if max(kcals) - min(kcals) > max(6.0, min(kcals) * 0.06):
                continue
            limpos = [f for f in itens if not any(r in _norm(f.name) for r in _RUIDO)]
            if not limpos:
                continue  # ninguém tem nome-base limpo: mantém todos
            limpos.sort(key=_qualidade)
            vencedor = limpos[0]
            for f in itens:
                if f.id != vencedor.id and f.id not in ja_escondidos:
                    escondidos.append((f, f"mesma comida que '{vencedor.name}' (só muda o sal)"))
                    ja_escondidos.add(f.id)

        # --- 3) AMBÍGUO ao lado de específicos --------------------------------
        # "Frango sobrecoxa assada" (232 kcal) convivendo com "…com pele assada"
        # (260) e "…sem pele assada" (233): o primeiro não diz se tem pele, então
        # é impossível escolher. Os específicos ficam, o ambíguo sai — que é
        # exatamente o que o usuário pediu ("ou especifique: esse aqui está cru").
        por_base: dict[str, list[Food]] = defaultdict(list)
        for f in visiveis:
            if f.id in ja_escondidos or not _sem_marca(f):
                continue
            por_base[_base_nua(f.name)].append(f)

        for base, itens in por_base.items():
            if len(itens) < 3:
                continue
            # Agrupa por conjunto de distintivos: se existem 2+ variantes
            # específicas e UMA sem nenhum distintivo relevante a mais, ela é a
            # ambígua.
            por_dist: dict[frozenset[str], list[Food]] = defaultdict(list)
            for f in itens:
                por_dist[_distintivos(f.name)].append(f)
            if len(por_dist) < 3:
                continue
            for dist, grupo in por_dist.items():
                # Existe outro conjunto que CONTÉM este e acrescenta informação?
                mais_especificos = [d for d in por_dist if d != dist and dist < d]
                if len(mais_especificos) >= 2:
                    for f in grupo:
                        if f.id not in ja_escondidos:
                            escondidos.append(
                                (f, f"ambíguo: existe versão específica de '{f.name}'")
                            )
                            ja_escondidos.add(f.id)

        # --- 4) GENÉRICO de UMA palavra, sem marca, no meio de vários irmãos ---
        # O caso que o usuário viu: um "Cuzcuz" de 125 kcal e um "Bolo" de 369,
        # sem marca, sem preparo, sem nada — no meio de dezenas de outros cuscuz e
        # bolos. Uma palavra só não dá pra escolher.
        #
        # UMA palavra, exatamente. A primeira versão desta regra aceitava até
        # duas e escondia "Pão italiano", "Pão ciabata", "Ovos caipira", "Bolo
        # mármore" — que são alimentos DIFERENTES, não duplicatas. O segundo termo
        # é justamente o que especifica; quem tem especificação fica.
        #
        # Restrito ao Open Food Facts de propósito: no TACO um nome curto é o
        # alimento BASE e é o certo; no OFF, onde toda linha é um produto de
        # rótulo, nome de uma palavra sem marca é registro incompleto.
        primeiro_token: dict[str, int] = defaultdict(int)
        for f in visiveis:
            tokens = _norm(f.name).split()
            if tokens:
                primeiro_token[tokens[0]] += 1

        for f in visiveis:
            if f.id in ja_escondidos or not _sem_marca(f):
                continue
            if f.source != FoodSource.OPEN_FOOD_FACTS:
                continue
            tokens = _norm(f.name).split()
            if len(tokens) != 1 or _distintivos(f.name):
                continue
            if primeiro_token[tokens[0]] >= 3:  # ele mesmo + 2 irmãos
                escondidos.append(
                    (f, f"genérico de uma palavra, sem marca, com "
                        f"{primeiro_token[tokens[0]] - 1} homônimos")
                )
                ja_escondidos.add(f.id)

        for f, motivo in escondidos:
            f.hidden = True

        db.commit()
        if recuperados:
            print(f"Alimentos: marca extraída do nome em {recuperados} produto(s) do Open Food Facts.")
        print(f"Alimentos: {len(escondidos)} escondido(s) de {len(visiveis)} visíveis.")
        for f, motivo in escondidos:
            print(f"  - id={f.id} '{f.name}' ({f.kcal_per_100g:.0f} kcal) — {motivo}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
