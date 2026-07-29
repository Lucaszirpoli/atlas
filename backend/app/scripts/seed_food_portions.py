"""Medidas caseiras dos alimentos (gramas/unidades da Parte 3.2).

Duas responsabilidades, ambas idempotentes e seguras em SQLite (dev) e Postgres
(prod):

1. `ensure_columns()` — adiciona unit_label/unit_amount em meal_log_items e
   saved_meal_items. create_all NÃO altera tabela que já existe, então num banco
   antigo essas colunas faltariam e qualquer registro de refeição estouraria.
   Roda cedo no init_db (antes de a API responder), como o padrão do ExerciseDB.

2. `run()` — cria a tabela food_portions (via create_all no init_db) e faz o
   BACKFILL: para cada alimento que já traz uma porção nomeada
   (default_portion_label + default_portion_g) e ainda não tem medida embutida,
   cria uma FoodPortion com o peso de UMA unidade. Assim ninguém perde a medida
   que já existia, e o app passa a oferecer "gramas OU <medida>".

Uso:  python -m app.scripts.seed_food_portions
"""

import re

from sqlalchemy import inspect, select, text

from app.core.db import SessionLocal, engine
from app.models.food import Food, FoodPortion

# Primeira palavra da medida no plural -> singular (espelha o pluralizar do app).
# "3 colheres de sopa" (45g) precisa virar a medida de UMA "colher de sopa" (15g).
_PLURAL_ES = ("r", "z")  # colheres->colher, cálices->cálice fica no ramo do 's'

# Rótulos genéricos demais pra virar medida caseira — melhor deixar só gramas.
_GENERICOS = {"porção", "porcao", "medida", "g", "grama", "gramas"}

# Primeira palavra que denuncia "isto é peso/volume, não medida caseira". Pega
# o que _GENERICOS não pega porque vem com sufixo: a TACO oficial rotula tudo
# como "100 g (referência TACO)", e sem isto derivávamos dali uma medida
# chamada "g (referência TACO)" pesando 1 g nos 597 alimentos da tabela.
# Espelha UNIDADES_DE_PESO em mobile/src/utils/portion.ts.
_UNIDADES_DE_PESO = {"g", "grama", "gramas", "mg", "kg", "ml", "l", "litro", "litros"}


def _singular_primeira(frase: str) -> str:
    palavras = frase.split()
    if not palavras:
        return frase
    w = palavras[0]
    if w.endswith("ões"):
        w = w[:-3] + "ão"
    elif w.endswith("es") and len(w) > 3 and w[-3] in _PLURAL_ES:
        w = w[:-2]  # colheres -> colher
    elif w.endswith("s") and len(w) > 2:
        w = w[:-1]  # conchas -> concha, fatias -> fatia, unidades -> unidade
    return " ".join([w, *palavras[1:]])


# O Open Food Facts guarda o serving em ingles e, muitas vezes, com o peso no
# proprio rotulo ("slice (50 g)", "each (70 g)"). Traduzimos o nome e usamos o
# peso do rotulo — antes o peso vinha do default_portion_g, que nesses casos
# caia em 100 g e produzia uma "fatia de 50 g" pesando 100 g na tela.
_TRADUCAO_SERVING = {
    # "serving"/"portion" viram "porção", que cai no filtro de rótulo genérico
    # logo abaixo — "1 porção" não diz nada a mais que as gramas.
    "serving": "porção",
    "portion": "porção",
    "slice": "fatia",
    "each": "unidade",
    "unit": "unidade",
    "piece": "pedaço",
    "cup": "xícara",
    "glass": "copo",
    "bottle": "garrafa",
    "can": "lata",
    "package": "pacote",
    "pack": "pacote",
    "bar": "barra",
    "tablespoon": "colher de sopa",
    "teaspoon": "colher de chá",
    "scoop": "dose",
}

# Peso escrito dentro do rotulo: "(50 g)", "50gm", "70 g".
_PESO_NO_ROTULO = re.compile(r"\(?\s*(\d+(?:[.,]\d+)?)\s*(g|gm|gr|ml)\b\s*\)?", re.IGNORECASE)


def _limpar_rotulo(frase: str) -> str | None:
    """Sobra do rotulo depois de tirar o peso: "slice (50 g)" -> "fatia".
    None quando o que sobra nao e uma medida utilizavel."""
    resto = _PESO_NO_ROTULO.sub(" ", frase)
    resto = resto.split("/")[0]  # "colheres/cuchara" -> "colheres"
    resto = re.sub(r"[()\[\],.;:]", " ", resto)
    resto = re.sub(r"\s+", " ", resto).strip().lower()
    if not resto or len(resto) > 30:
        return None
    if not re.fullmatch(r"[a-zà-ÿ ]+", resto):
        return None
    resto = _TRADUCAO_SERVING.get(resto, resto)
    if resto in _GENERICOS or resto.split()[0] in _UNIDADES_DE_PESO:
        return None
    return resto


def parse_portion(label: str | None, portion_g: float | None) -> tuple[str, float] | None:
    """('3 colheres de sopa', 45.0) -> ('colher de sopa', 15.0).
    ('1 unidade', 50.0) -> ('unidade', 50.0). ('fatia', 25.0) -> ('fatia', 25.0).
    Retorna None quando não dá pra derivar uma medida útil."""
    if not label or not portion_g or portion_g <= 0:
        return None
    texto = label.strip()
    m = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s+(.*\S)\s*$", texto)
    if m:
        n = float(m.group(1).replace(",", "."))
        frase = m.group(2)
    else:
        n = 1.0
        frase = texto
    if n <= 0 or not frase:
        return None

    # Peso escrito no proprio rotulo manda: e o dado do fabricante. Sem isto,
    # "slice (50 g)" virava uma fatia pesando o default_portion_g (100 g) —
    # a medida contradizia o proprio nome.
    peso = _PESO_NO_ROTULO.search(frase)
    if peso:
        limpo = _limpar_rotulo(frase)
        if limpo is None:
            return None
        gramas = float(peso.group(1).replace(",", ".")) / (n if n > 1 else 1)
        if gramas <= 0 or gramas > 5000:
            return None
        return _singular_primeira(limpo)[:50], round(gramas, 2)

    grams_one = portion_g / n
    if grams_one <= 0 or grams_one > 5000:
        return None
    if n != 1.0:
        frase = _singular_primeira(frase)
    # Rótulos genéricos demais ("porção", "medida") não ajudam — melhor só gramas.
    if frase.lower() in _GENERICOS:
        return None
    if frase.split()[0].lower() in _UNIDADES_DE_PESO:
        return None
    # "50g", "20 g", "330ml": o rótulo JÁ É um peso, não uma medida caseira. Vem
    # do campo serving do Open Food Facts e virava uma "medida" chamada "50g"
    # pesando outra coisa ("50g = 100 g") — o pior tipo de mentira na tela.
    if re.fullmatch(r"\d+(?:[.,]\d+)?\s*(?:g|kg|mg|ml|l)", frase.strip(), re.IGNORECASE):
        return None
    return frase[:50], round(grams_one, 2)


def _limpar_medidas_de_peso(db) -> int:
    """Apaga as medidas embutidas que nunca deveriam ter sido criadas — as
    derivadas de um rótulo de peso ("g (referência TACO)"). Só mexe nas
    embutidas (created_by_user_id nulo); medida que o usuário criou é dele,
    mesmo que ele tenha chamado de "g"."""
    alvo = [
        p
        for p in db.execute(
            select(FoodPortion).where(FoodPortion.created_by_user_id.is_(None))
        ).scalars()
        if (p.label.split() and p.label.split()[0].lower() in _UNIDADES_DE_PESO)
        or re.fullmatch(r"\d+(?:[.,]\d+)?\s*(?:g|kg|mg|ml|l)", p.label.strip(), re.IGNORECASE)
    ]
    for p in alvo:
        db.delete(p)
    return len(alvo)


def ensure_columns() -> None:
    pg = engine.dialect.name == "postgresql"
    alvo = {
        "meal_log_items": {c["name"] for c in inspect(engine).get_columns("meal_log_items")},
        "saved_meal_items": {c["name"] for c in inspect(engine).get_columns("saved_meal_items")},
    }
    cols = [("unit_label", "VARCHAR(50)"), ("unit_amount", "DOUBLE PRECISION" if pg else "FLOAT")]
    with engine.begin() as conn:
        for tabela, existentes in alvo.items():
            for col, tipo in cols:
                if col in existentes:
                    continue
                if pg:
                    conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS {col} {tipo}"))
                else:
                    conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}"))


def run() -> None:
    # No init_db o create_all já criou food_portions antes daqui; rodando este
    # script sozinho (o uso documentado acima) a tabela pode não existir ainda.
    # checkfirst=True não recria se já estiver lá.
    FoodPortion.__table__.create(bind=engine, checkfirst=True)
    ensure_columns()
    db = SessionLocal()
    try:
        # Limpa ANTES de calcular quem já tem medida: um alimento cuja única
        # medida embutida era a lixeira do "g (referência TACO)" precisa voltar
        # a ser candidato ao backfill (e vai ser corretamente pulado agora).
        removidas = _limpar_medidas_de_peso(db)
        db.flush()

        # Só alimentos que ainda não têm NENHUMA medida embutida (dono nulo).
        com_medida = set(
            db.execute(
                select(FoodPortion.food_id).where(FoodPortion.created_by_user_id.is_(None))
            ).scalars()
        )
        criadas = 0
        for food in db.execute(select(Food)).scalars():
            if food.id in com_medida:
                continue
            parsed = parse_portion(food.default_portion_label, food.default_portion_g)
            if parsed is None:
                continue
            label, grams = parsed
            db.add(
                FoodPortion(
                    food_id=food.id,
                    label=label,
                    grams=grams,
                    created_by_user_id=None,
                    sort_order=0,
                )
            )
            criadas += 1
        db.commit()
        print(f"Medidas caseiras embutidas criadas: {criadas}, removidas: {removidas}.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
