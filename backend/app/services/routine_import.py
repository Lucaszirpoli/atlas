"""Importa rotinas de outros apps de treino (Hevy, Strong, Jefit...) via CSV.

POR QUE EXISTE: perder o treino montado é a maior barreira pra alguém trocar de
app. Quem tem a rotina pronta no Hevy não vai redigitar 5 treinos pra
experimentar o ATLAS.

O QUE IMPORTA: as ROTINAS (os moldes). O histórico não — é append-only (regra 4
do CLAUDE.md) e misturar sessão importada com sessão real bagunçaria os
gráficos de evolução.

A PARTE PERIGOSA é casar "Bench Press (Barbell)" com "Supino reto com barra".
Casar por semelhança de texto sozinha é o mesmo erro que colocou GIF de
agachamento no leg press: aqui, erraria o histórico de supino pra crucifixo,
em silêncio. Por isso este módulo NÃO grava nada — ele devolve o que casou e
com que confiança, e a tela pede confirmação antes de salvar.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exercise import STRENGTH_CATEGORIES, Exercise

# Confiança mínima pra sugerir um par. Abaixo disso não sugerimos nada — é
# melhor a pessoa escolher do que a gente chutar o exercício errado.
_MIN_CONFIANCA = 0.45
# A partir daqui consideramos "casou" e não pedimos atenção especial na revisão.
_CONFIANCA_ALTA = 0.75

# Termo em inglês -> termo brasileiro. Casar "bench press" com "supino" por
# semelhança de LETRAS é impossível (não têm nada em comum): a ponte tem que
# ser de vocabulário. Ordem importa — frase maior primeiro.
_GLOSSARIO: list[tuple[str, str]] = [
    ("incline bench press", "supino inclinado"),
    ("decline bench press", "supino declinado"),
    ("bench press", "supino reto"),
    ("chest press", "supino máquina"),
    ("chest fly", "crucifixo"),
    ("pec deck", "peck deck"),
    ("cable crossover", "crossover"),
    ("lat pulldown", "puxada frontal"),
    ("pull up", "barra fixa"),
    ("pull-up", "barra fixa"),
    ("chin up", "barra fixa supinada"),
    ("seated row", "remada sentada"),
    ("bent over row", "remada curvada"),
    ("barbell row", "remada curvada"),
    ("dumbbell row", "remada unilateral"),
    ("t bar row", "remada cavalinho"),
    ("face pull", "face pull"),
    ("shoulder press", "desenvolvimento"),
    ("overhead press", "desenvolvimento militar"),
    ("military press", "desenvolvimento militar"),
    ("lateral raise", "elevação lateral"),
    ("front raise", "elevação frontal"),
    ("rear delt", "crucifixo invertido"),
    ("shrug", "encolhimento"),
    ("bicep curl", "rosca direta"),
    ("biceps curl", "rosca direta"),
    ("hammer curl", "rosca martelo"),
    ("preacher curl", "rosca scott"),
    ("concentration curl", "rosca concentrada"),
    ("triceps pushdown", "tríceps pulley"),
    ("tricep pushdown", "tríceps pulley"),
    ("triceps extension", "extensão de tríceps"),
    ("skullcrusher", "tríceps testa"),
    ("skull crusher", "tríceps testa"),
    ("close grip bench", "supino pegada fechada"),
    ("dip", "mergulho"),
    ("squat", "agachamento"),
    ("front squat", "agachamento frontal"),
    ("hack squat", "agachamento hack"),
    ("leg press", "leg press"),
    ("leg extension", "cadeira extensora"),
    ("leg curl", "mesa flexora"),
    ("romanian deadlift", "levantamento terra romeno"),
    ("stiff leg deadlift", "stiff"),
    ("deadlift", "levantamento terra"),
    ("hip thrust", "elevação pélvica"),
    ("glute bridge", "ponte de glúteo"),
    ("lunge", "afundo"),
    ("bulgarian split squat", "agachamento búlgaro"),
    ("calf raise", "panturrilha"),
    ("calf press", "panturrilha no leg press"),
    ("standing calf", "panturrilha em pé"),
    ("seated calf", "panturrilha sentado"),
    ("crunch", "abdominal"),
    ("plank", "prancha"),
    ("russian twist", "rotação russa"),
    ("leg raise", "elevação de pernas"),
    ("pullover", "pullover"),
    ("good morning", "good morning"),
    ("thruster", "thruster"),
    ("barbell", "barra"),
    ("dumbbell", "halteres"),
    ("machine", "máquina"),
    ("cable", "cabo"),
    ("smith machine", "smith"),
    ("kettlebell", "kettlebell"),
    ("band", "faixa"),
    ("bodyweight", "livre"),
    ("seated", "sentado"),
    ("standing", "em pé"),
    ("incline", "inclinado"),
    ("decline", "declinado"),
    ("close grip", "pegada fechada"),
    ("wide grip", "pegada aberta"),
    ("reverse", "inverso"),
    ("single arm", "unilateral"),
    ("one arm", "unilateral"),
    ("single leg", "unilateral"),
]


def _normalizar(texto: str) -> str:
    """Minúsculas, sem acento, sem pontuação, espaços colapsados."""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Frase MAIOR primeiro, sempre. Sem isto "squat" casa dentro de "bulgarian
# split squat" e consome a frase antes da entrada específica ter chance —
# "Bulgarian Split Squat" virava "bulgarian split agachamento" e não achava par
# nenhum, mesmo com o termo certo no glossário. Ordenar aqui (e não confiar na
# ordem em que foram escritos) evita que a próxima entrada adicionada reabra o bug.
_GLOSSARIO_ORDENADO = sorted(_GLOSSARIO, key=lambda p: -len(p[0]))


def traduzir_nome(nome_en: str) -> str:
    """Passa o nome do app estrangeiro pro vocabulário brasileiro.

    O Hevy escreve "Bench Press (Barbell)". Sem esta ponte, comparar com
    "Supino reto com barra" por semelhança de letras dá quase zero — as duas
    frases não compartilham praticamente nenhum caractere.
    """
    t = _normalizar(nome_en)
    for en, pt in _GLOSSARIO_ORDENADO:
        t = re.sub(rf"\b{re.escape(en)}\b", pt, t)
    return _normalizar(t)


def _tokens(texto: str) -> set[str]:
    # Palavras de ligação não ajudam a distinguir exercício nenhum.
    stop = {"com", "de", "do", "da", "no", "na", "em", "o", "a", "e", "para"}
    return {w for w in _normalizar(texto).split() if w not in stop and len(w) > 1}


def confianca(nome_importado: str, exercicio: Exercise) -> float:
    """0..1 de quão provável é que os dois sejam o MESMO exercício.

    Usa sobreposição de palavras (Jaccard ponderado) sobre o nome já traduzido,
    não semelhança de caracteres: "supino reto" e "supino inclinado" têm letras
    quase idênticas mas são exercícios diferentes — o que os separa é a palavra
    "inclinado", e é isso que precisa pesar.
    """
    a = _tokens(traduzir_nome(nome_importado))
    b = _tokens(exercicio.name)
    if not a or not b:
        return 0.0
    comuns = a & b
    if not comuns:
        return 0.0
    # Proporção do que o importado pede que o candidato tem, penalizando
    # candidato com muita palavra sobrando (é outro exercício, mais específico).
    cobertura = len(comuns) / len(a)
    excesso = len(b - a) / max(len(b), 1)
    return max(0.0, cobertura - excesso * 0.35)


@dataclass
class ExercicioImportado:
    nome_original: str
    exercise_id: int | None = None
    exercise_nome: str | None = None
    confianca: float = 0.0
    # True quando a confiança é baixa: a tela destaca pra pessoa conferir.
    revisar: bool = True
    series: int = 3
    reps_min: int = 8
    reps_max: int | None = 12


@dataclass
class RotinaImportada:
    nome: str
    exercicios: list[ExercicioImportado] = field(default_factory=list)


def _catalogo(db: Session) -> list[Exercise]:
    return list(
        db.execute(
            select(Exercise).where(
                Exercise.is_custom.is_(False),
                Exercise.category.in_(STRENGTH_CATEGORIES),
            )
        ).scalars()
    )


def casar_exercicio(nome: str, catalogo: list[Exercise]) -> ExercicioImportado:
    """Acha o melhor par pro nome vindo do outro app."""
    melhor: Exercise | None = None
    melhor_nota = 0.0
    for ex in catalogo:
        nota = confianca(nome, ex)
        if nota > melhor_nota:
            melhor, melhor_nota = ex, nota

    if melhor is None or melhor_nota < _MIN_CONFIANCA:
        # Nada confiável: devolve sem par. A tela oferece escolher na mão ou
        # cadastrar um exercício próprio — melhor que atribuir o errado.
        return ExercicioImportado(nome_original=nome)
    return ExercicioImportado(
        nome_original=nome,
        exercise_id=melhor.id,
        exercise_nome=melhor.name,
        confianca=round(melhor_nota, 2),
        revisar=melhor_nota < _CONFIANCA_ALTA,
    )


# Colunas conhecidas por app. O Hevy exporta histórico (uma linha por série);
# o título do treino é o nome da rotina e as séries de um exercício se repetem.
_COL_ROTINA = ("title", "workout_name", "routine", "workout", "nome")
_COL_EXERCICIO = ("exercise_title", "exercise_name", "exercise", "exercicio")
_COL_REPS = ("reps", "repetitions", "repeticoes")


def _achar_coluna(cabecalho: list[str], candidatas: tuple[str, ...]) -> str | None:
    norm = {_normalizar(c).replace(" ", "_"): c for c in cabecalho}
    for cand in candidatas:
        if cand in norm:
            return norm[cand]
    return None


def parse_csv(db: Session, conteudo: str) -> list[RotinaImportada]:
    """Lê o CSV exportado e devolve as rotinas propostas (NÃO grava nada).

    Funciona com o formato do Hevy e com qualquer CSV que tenha uma coluna de
    nome de treino e uma de nome de exercício — o suficiente pra cobrir Strong,
    Jefit e afins sem um parser por app.
    """
    amostra = conteudo[:4096]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t")
    except csv.Error:
        dialeto = csv.excel  # CSV de uma coluna só, ou separador exótico
    leitor = csv.DictReader(io.StringIO(conteudo), dialect=dialeto)
    if not leitor.fieldnames:
        return []

    col_rotina = _achar_coluna(list(leitor.fieldnames), _COL_ROTINA)
    col_exercicio = _achar_coluna(list(leitor.fieldnames), _COL_EXERCICIO)
    if not col_exercicio:
        return []
    col_reps = _achar_coluna(list(leitor.fieldnames), _COL_REPS)

    # nome da rotina -> nome do exercício -> nº de séries (linhas repetidas) e reps
    agrupado: dict[str, dict[str, list[int]]] = {}
    for linha in leitor:
        ex_nome = (linha.get(col_exercicio) or "").strip()
        if not ex_nome:
            continue
        rot_nome = (linha.get(col_rotina) or "Treino importado").strip() or "Treino importado"
        reps = 0
        if col_reps:
            try:
                reps = int(float(linha.get(col_reps) or 0))
            except (TypeError, ValueError):
                reps = 0
        agrupado.setdefault(rot_nome, {}).setdefault(ex_nome, []).append(reps)

    catalogo = _catalogo(db)
    rotinas: list[RotinaImportada] = []
    for rot_nome, exs in agrupado.items():
        rotina = RotinaImportada(nome=rot_nome[:150])
        for ex_nome, reps_list in exs.items():
            item = casar_exercicio(ex_nome, catalogo)
            # Nº de linhas do mesmo exercício = nº de séries que a pessoa fez.
            item.series = max(1, min(len(reps_list), 10))
            reais = [r for r in reps_list if r > 0]
            if reais:
                item.reps_min = min(reais)
                item.reps_max = max(reais) if max(reais) != min(reais) else None
            rotina.exercicios.append(item)
        if rotina.exercicios:
            rotinas.append(rotina)
    return rotinas
