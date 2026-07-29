"""Medidas caseiras curadas + supressão de alimentos duplicados.

Resolve duas queixas concretas da busca de alimentos:

1. **Alimento sem unidade.** A TACO oficial só publica valores por 100 g, então
   os 597 itens dela entravam no app sem NENHUMA medida caseira: "Pão trigo
   francês" só podia ser registrado em gramas. Ninguém pesa um pão — pensa "um
   pão". `app/data/medidas_caseiras.json` traz a curadoria (peso de UMA unidade
   de cada medida) e este script materializa isso em FoodPortion.

2. **Alimento repetido com kcal diferente.** O seed curado (taco_seed.csv) e a
   TACO oficial trazem os mesmos alimentos: buscar "pão" devolvia "Pão francês"
   (300 kcal, com medida) e "Pão trigo francês" (299,8 kcal, sem medida) — a
   mesma coisa, parecendo duas. O duplicado perdedor é marcado `hidden`, não
   apagado: o histórico de refeições aponta pra ele e é append-only.

Idempotente. Roda sozinho no init_db.

Uso:  python -m app.scripts.seed_medidas_caseiras
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from sqlalchemy import inspect, select, text

from app.core.db import SessionLocal, engine
from app.models.food import Food, FoodPortion, FoodSource

JSON_MEDIDAS = Path(__file__).parent.parent / "data" / "medidas_caseiras.json"
JSON_TACO = Path(__file__).parent.parent / "data" / "taco_official.json"


def _norm(texto: str) -> str:
    """minúsculo, sem acento e SEM PONTUAÇÃO — mesma normalização das regras.

    Tirar a vírgula é essencial: a TACO descreve os alimentos como "Banana,
    nanica, crua", e a regra que procura "banana nanica" não casava com isso —
    toda banana caía no peso genérico em vez do peso da sua variedade."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn"
    )
    limpo = re.sub(r"[,;.]+", " ", sem_acento.lower())
    return re.sub(r"\s+", " ", limpo).strip()


def ensure_columns() -> None:
    """Adiciona foods.hidden num banco que já existe. create_all não altera
    tabela existente, então sem isto o app quebraria ao ler a coluna."""
    cols = {c["name"] for c in inspect(engine).get_columns("foods")}
    if "hidden" in cols:
        return
    pg = engine.dialect.name == "postgresql"
    tipo = "BOOLEAN NOT NULL DEFAULT FALSE" if pg else "BOOLEAN NOT NULL DEFAULT 0"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE foods ADD COLUMN hidden {tipo}"))


def _casa(nome_norm: str, regra: dict) -> bool:
    if not all(termo in nome_norm for termo in regra["nome"]):
        return False
    return not any(termo in nome_norm for termo in regra.get("excluir", []))


def _medidas_para(nome: str, categoria: str | None, regras: list[dict], padroes: dict) -> list[tuple[str, float]]:
    """A PRIMEIRA regra que casar vence — as específicas vêm antes das genéricas
    no JSON. Sem regra nenhuma, cai no padrão da categoria da TACO."""
    n = _norm(nome)
    for regra in regras:
        if _casa(n, regra):
            return [(label, float(g)) for label, g in regra["medidas"]]
    padrao = padroes.get(categoria or "")
    if padrao:
        return [(label, float(g)) for label, g in padrao]
    return []


def _porcao_padrao_inutil(label: str | None) -> bool:
    """True quando o rótulo da porção padrão não é uma medida caseira de
    verdade: vazio, ou só um peso ("100 g", "100 g (referência TACO)", "50gm").
    Espelha o filtro de seed_food_portions.parse_portion."""
    if not label or not label.strip():
        return True
    # Tira um número inicial e qualquer parêntese explicativo: "100 g
    # (referência TACO)" -> "g", "50gm" -> "gm", "2 fatias" -> "fatias".
    texto = re.sub(r"\(.*?\)", " ", _norm(label))
    texto = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*", "", texto).strip()
    primeira = texto.split(" ")[0] if texto else ""
    return primeira in {"g", "gm", "gr", "grama", "gramas", "mg", "kg", "ml", "l", "litro", "litros"}


def _aplicar_medidas(db, categorias: dict[str, str], regras, padroes) -> tuple[int, int]:
    """Cria as medidas que faltam. Nunca mexe em alimento que já tem medida
    embutida — o seed curado é mais confiável que qualquer regra genérica."""
    ja_tem = set(
        db.execute(select(FoodPortion.food_id).where(FoodPortion.created_by_user_id.is_(None))).scalars()
    )
    criadas = 0
    alimentos = 0
    for food in db.execute(select(Food)).scalars():
        if food.id in ja_tem:
            continue
        medidas = _medidas_para(food.name, categorias.get(food.external_id or ""), regras, padroes)
        if not medidas:
            continue
        alimentos += 1

        # A medida também vira a PORÇÃO PADRÃO do alimento quando ele não tinha
        # nenhuma útil. Sem isto o app continuaria abrindo "Pão de soja" em
        # "100 g": a busca e a ficha leem default_portion_*, não food_portions.
        # Só sobrescreve rótulo de peso ("100 g (referência TACO)") ou vazio —
        # porção curada de verdade ("2 fatias") é melhor e fica como está.
        if _porcao_padrao_inutil(food.default_portion_label):
            label, grams = medidas[0]
            food.default_portion_label = f"1 {label}"
            food.default_portion_g = grams

        for ordem, (label, grams) in enumerate(medidas):
            db.add(
                FoodPortion(
                    food_id=food.id,
                    label=label,
                    grams=grams,
                    created_by_user_id=None,
                    sort_order=ordem,
                )
            )
            criadas += 1
    return criadas, alimentos


def _pontuacao(food: Food, tem_medida: bool) -> tuple:
    """Qual gêmeo fica visível. Ordem de desempate:
    1. tem medida caseira (o seed curado tem, a TACO oficial não);
    2. mais campos nutricionais preenchidos (fibra/sódio/açúcar) — entre dois
       produtos anônimos do Open Food Facts, o mais completo é o mais confiável;
    3. não é da TACO oficial (o curado usa nome que a pessoa realmente digita —
       "Pão francês", não "Pão trigo francês");
    4. id menor, só pra ser determinístico."""
    oficial = (food.external_id or "").startswith("TACO-OFF-")
    completude = sum(
        1
        for v in (food.fiber_g_per_100g, food.sodium_mg_per_100g, food.sugar_g_per_100g)
        if v is not None
    )
    return (0 if tem_medida else 1, -completude, 1 if oficial else 0, food.id)


def _suprimir_duplicados(db) -> int:
    """Esconde o gêmeo perdedor de cada nome repetido. `hidden` em vez de
    DELETE porque meal_log_items referencia o alimento e o histórico é
    append-only — apagar reescreveria o passado da pessoa."""
    com_medida = set(
        db.execute(select(FoodPortion.food_id).where(FoodPortion.created_by_user_id.is_(None))).scalars()
    )
    por_nome: dict[str, list[Food]] = {}
    for food in db.execute(select(Food)).scalars():
        if food.source == FoodSource.TACO:
            por_nome.setdefault(_norm(food.name), []).append(food)
        elif food.source == FoodSource.OPEN_FOOD_FACTS and not (food.brand or "").strip():
            # Produto do Open Food Facts SEM MARCA: o nome é tudo que a pessoa
            # vê. Dois "Cuzcuz" com 125 e 340 kcal viram duas linhas idênticas
            # na busca, impossíveis de distinguir — e uma delas está errada. Com
            # marca eles ficam (aí a linha diferencia); sem marca, sobra um.
            por_nome.setdefault(f"off:{_norm(food.name)}", []).append(food)

    escondidos = 0
    for gemeos in por_nome.values():
        if len(gemeos) < 2:
            continue
        gemeos.sort(key=lambda f: _pontuacao(f, f.id in com_medida))
        for perdedor in gemeos[1:]:
            if not perdedor.hidden:
                perdedor.hidden = True
                escondidos += 1
        if gemeos[0].hidden:
            gemeos[0].hidden = False  # garante que o vencedor esteja visível
    return escondidos


def run() -> None:
    ensure_columns()
    dados = json.loads(JSON_MEDIDAS.read_text(encoding="utf-8"))
    regras = dados["regras"]
    padroes = {k: v for k, v in dados["_padroes_por_categoria"].items() if k != "_doc"}
    categorias = {
        f"TACO-OFF-{r['id']}": r.get("category") for r in json.loads(JSON_TACO.read_text(encoding="utf-8"))
    }

    db = SessionLocal()
    try:
        escondidos = _suprimir_duplicados(db)
        db.flush()
        criadas, alimentos = _aplicar_medidas(db, categorias, regras, padroes)
        db.commit()
        print(f"Medidas caseiras: {criadas} criadas em {alimentos} alimentos.")
        print(f"Duplicados escondidos da busca: {escondidos}.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
