"""Os TRILHOS do treino que o coach monta — parâmetros de máquina, não texto.

`MethodSpec` descreve um plano de treino em números que o motor determinístico
(`methods_engine`) sabe executar: frequência, split por nº de dias, séries,
reps, descanso, RIR, proporção composto/isolado e regra de progressão. O
montador constrói o esqueleto a partir disso e uma validação rejeita qualquer
plano que viole os trilhos.

`coach_custom_spec()` é a única spec que existe hoje: o plano do coach,
baseado em ciência e adaptado ao objetivo da pessoa. As regras de SELEÇÃO e
ORGANIZAÇÃO dos exercícios (tiers, padrão de movimento, ordem da sessão,
anti-redundância, cobertura regional) vivem em `exercise_taxonomy` e no motor —
aqui ficam só os números da sessão.

HISTÓRICO: este módulo hospedava a base estruturada das 10 metodologias da
Arvo (DC, Mentzer, Kuba, FST-7, Mountain Dog, Y3T, RP, 5/3/1, Juggernaut,
Westside), usada pelo AI Hub. Os 10 métodos foram retirados do produto em
2026-07-30 — o coach passou a ter regra própria pra tudo — e com eles saíram o
registro `METHODS`, `get_method`, `list_methods`, `recommend_method_for_profile`
e a base `arvo_methods_report.txt`. Alguns campos de `MethodSpec` (phases,
forbidden, schedule_suggestions, guide_excerpt) só existiam pra sustentar
aquela fidelidade e hoje ficam vazios no plano do coach.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Experience(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ProgressionFamily(str, Enum):
    """As quatro famílias de progressão do relatório (regra transversal)."""

    LOAD_OR_REPS = "load_or_reps"  # DC, Mentzer: + reps/carga; correção = mais descanso
    VOLUME_LANDMARKS = "volume_landmarks"  # Kuba, RP: + sets/reps por RIR e landmarks
    DENSITY_QUALITY = "density_quality"  # FST-7, Y3T, Mountain Dog: densidade/pump/técnica
    TM_AMRAP = "tm_amrap"  # 5/3/1, Juggernaut, Westside: TM, AMRAP, percentuais


@dataclass(frozen=True)
class Phase:
    """Uma fase dentro de uma SESSÃO (Mountain Dog) ou de uma SEMANA/ciclo
    (Y3T, FST-7). Carrega os parâmetros que valem só naquela fase."""

    name: str
    reps: str  # faixa, ex "8-12" ou "15-30+"
    sets: str  # ex "2-3" ou "7"
    rir: str | None = None
    tempo: str | None = None  # cadência, ex "3-1-1-1"
    rest_seconds: str | None = None  # ex "30-45" ou "180-240"
    intensity_pct_1rm: str | None = None  # ex "70-85"
    note: str | None = None


@dataclass(frozen=True)
class MethodSpec:
    key: str
    name: str
    author: str
    goal: str
    experience_min: Experience
    progression_family: ProgressionFamily

    # Frequência / agenda -----------------------------------------------------
    # dias por semana suportados (o motor casa com a disponibilidade do user)
    days_per_week: tuple[int, ...] = ()
    # sugestões de agenda por nº de dias (fidelidade: Mentzer 2d = ter/sex)
    schedule_suggestions: dict[int, list[str]] = field(default_factory=dict)
    frequency_per_muscle: str | None = None  # ex "~2x/sem", "1x/sem", "a cada 4-5 dias"
    split_by_days: dict[int, list[str]] = field(default_factory=dict)

    # Parâmetros base da sessão (quando o método é uniforme; senão ver phases)
    sets_per_exercise: str | None = None
    reps: str | None = None
    tempo: str | None = None
    rest_seconds: str | None = None
    rir: str | None = None
    exercises_per_session: str | None = None

    # A REGRA MATEMÁTICA que a IA sempre errava: proporção dentro da sessão.
    # Fração de exercícios COMPOSTOS por sessão (o resto é isolamento). Aplicada
    # intra-treino, harmonicamente — nunca "tudo composto no dia 1".
    compound_ratio: float | None = None  # ex Kuba 0.40, Mentzer 0.90

    # Estrutura multifásica (por sessão OU por semana/ciclo)
    phase_scope: str | None = None  # "session" | "week" | None
    phases: tuple[Phase, ...] = ()

    # Ciclo / periodização ----------------------------------------------------
    mesocycle_weeks: str | None = None
    deload_rule: str | None = None
    progression_rule: str = ""

    # Regras de segurança / proibições (o motor bloqueia sugestões que violem)
    forbidden: tuple[str, ...] = ()  # descrições legíveis das proibições
    equipment_pref: str | None = None
    coaching_notes: tuple[str, ...] = ()

    # Quando um FOCO se repete na semana (ex.: "superior" duas vezes num split de
    # 4 dias), True mantém a MESMA seleção de exercício nas duas ocorrências —
    # correto pros métodos consagrados, cujo A/B é uma sessão fixa que se repete
    # de propósito (DC Training, Mentzer 2d). O plano do coach usa False: cada
    # ocorrência escolhe de novo (dentro do que ainda não foi usado na semana),
    # dando variação real de exercício — é o que evita "só uma remada curvada
    # no treino inteiro" quando dá pra variar pra remada na máquina no repeat.
    repeat_same_session: bool = True

    # Trecho-fonte do relatório (camada RAG: a IA cita daqui, nunca inventa)
    guide_excerpt: str = ""


# ---------------------------------------------------------------------------
# PLANO DO COACH — o treino que o coach monta, baseado em ciência e adaptado ao
# objetivo, em qualquer frequência de 2 a 6 dias. É o único plano que existe:
# determinístico e usando só exercícios reais da base (o montador nunca inventa
# exercício — regra do produto).
# ---------------------------------------------------------------------------

# Split por nº de dias, desenhado pra 2×/semana por grupo (regra 6: nada de
# bro-split como padrão). Os rótulos batem com session_blueprints.BLUEPRINTS —
# cada um tem uma sequência explícita de vagas, com padrão de movimento e papel.
#
# As divisões são as que a regra mestra descreve, uma por frequência:
_COACH_SPLITS: dict[int, list[str]] = {
    # 2 dias: full body A/B. Não é o ideal (a regra mestra não trata 2 dias),
    # mas é treino de verdade — e como as duas sessões são full body, cada
    # grupo ainda é treinado 2×/semana. A e B juntos já fecham peito
    # clavicular+esternal, costas dorsais+upper back e as duas funções do
    # posterior.
    2: ["full body a", "full body b"],
    # 3 dias: FULL BODY ×3, como a regra mestra prescreve ("Full Body 3x por
    # semana"). Cada sessão tem dominante de joelho, dominante de quadril, um
    # empurrar, uma puxada, um isolador e panturrilha/core — e os três dias
    # variam os padrões pra distribuir o estresse.
    3: ["full body a", "full body b", "full body c"],
    # 4 dias: upper/lower A/B. A puxa horizontal (superior) e joelho
    # (inferior); B puxa vertical e quadril. Ver também TORSO_LIMBS_SPLIT, que
    # substitui este quando o ponto fraco é braço ou panturrilha.
    4: ["superior a", "inferior a", "superior b", "inferior b"],
    # 5 dias: PPL + upper/lower. Os dois últimos dias são EQUILIBRADOS
    # (empurrar e puxar juntos) porque a função deles é preencher lacuna de
    # volume, não repetir a ênfase de um dia de push ou de pull.
    5: ["push a", "pull a", "pernas a", "superior", "inferior"],
    # 6 dias: PPL ×2, com a segunda passagem trocando qual padrão lidera (o
    # sufixo b) — a regra mestra pede variação na segunda passagem, não
    # repetição literal.
    6: ["push a", "pull a", "pernas a", "push b", "pull b", "pernas b"],
    # 7 dias NÃO existe de propósito: sem dia de folga não há recuperação, e a
    # fadiga que o motor administra é sistêmica. Ver TRAINING_DAYS_MAX.
}

# Alternativa de 4 dias (regra mestra, "Torso / Limbs"). O tronco fica só com
# empurrar/puxar e as pernas dividem o dia com os braços — é o desenho que
# "permite maior volume para músculos menores sem sobrecarregar as sessões de
# tronco". O coach só troca pra ela quando o ponto fraco é justamente um
# músculo menor (bíceps, tríceps ou panturrilha); fora disso ela não compra
# nada sobre upper/lower e só mudaria o treino por mudar.
TORSO_LIMBS_SPLIT: list[str] = ["torso a", "membros a", "torso b", "membros b"]

# Pontos fracos que fazem o Torso/Limbs valer a pena.
TORSO_LIMBS_WEAK_POINTS: frozenset[str] = frozenset({"biceps", "triceps", "calves"})


def coach_split_for(days: int, weak_points: list[str] | None = None) -> list[str]:
    """O split do coach pra `days` dias, já considerando ponto fraco.

    Só um caso muda a divisão: 4 dias com ponto fraco em músculo menor vira
    Torso/Limbs. Todo o resto é o mapa acima.
    """
    if days == 4 and any(w in TORSO_LIMBS_WEAK_POINTS for w in (weak_points or [])):
        return list(TORSO_LIMBS_SPLIT)
    base = _COACH_SPLITS.get(days)
    if base:
        return list(base)
    # Frequência fora de 2–6 não deveria chegar aqui (o builder faz clamp), mas
    # se chegar, repete o ciclo de 3 dias em vez de estourar.
    ciclo = _COACH_SPLITS[3]
    return [ciclo[i % len(ciclo)] for i in range(max(1, days))]

# Parâmetros da sessão por objetivo — proporção composto/isolado, RIR, descanso.
# REPS: o coach trabalha com 8-12 em todo objetivo (a faixa-padrão de
# hipertrofia, o consenso mais robusto de estímulo x recuperação x adesão) —
# não varia por objetivo; o que muda é ratio/rir/descanso.
_COACH_REPS = "8-12"
_COACH_GOAL_PARAMS: dict[str, dict] = {
    "hipertrofia": {"reps": _COACH_REPS, "ratio": 0.5, "rir": "1-2", "rest": "90-120",
                    "family": ProgressionFamily.VOLUME_LANDMARKS,
                    "goal_txt": "Hipertrofia geral com sobrecarga progressiva e volume 2×/semana por grupo."},
    "emagrecimento": {"reps": _COACH_REPS, "ratio": 0.45, "rir": "1-2", "rest": "60-90",
                      "family": ProgressionFamily.DENSITY_QUALITY,
                      "goal_txt": "Preservar músculo no déficit com densidade e a mesma faixa de reps de sempre."},
    "recomposicao": {"reps": _COACH_REPS, "ratio": 0.5, "rir": "1-2", "rest": "75-90",
                     "family": ProgressionFamily.VOLUME_LANDMARKS,
                     "goal_txt": "Recomposição: força e volume equilibrados, 2×/semana por grupo."},
    "manutencao": {"reps": _COACH_REPS, "ratio": 0.5, "rir": "2", "rest": "90",
                   "family": ProgressionFamily.VOLUME_LANDMARKS,
                   "goal_txt": "Manter massa e força com um estímulo consistente e sustentável."},
    "performance": {"reps": _COACH_REPS, "ratio": 0.6, "rir": "2-3", "rest": "150-180",
                    "family": ProgressionFamily.LOAD_OR_REPS,
                    "goal_txt": "Força e performance: mais compostos e descanso maior, mesma faixa de reps."},
}


def coach_custom_spec(goal: str | None, experience: str | None = None) -> MethodSpec:
    """O plano do coach pra um objetivo, pronto pra qualquer frequência 2–6.
    Alimenta o motor determinístico (build_plan/validate_plan) com os trilhos da
    sessão (split por dia, reps, proporção). experience_min fica em BEGINNER de
    propósito: o volume real vem do tempo por sessão, não de travar por nível."""
    p = _COACH_GOAL_PARAMS.get(goal or "", _COACH_GOAL_PARAMS["hipertrofia"])
    return MethodSpec(
        key="coach_custom",
        name="Plano do coach",
        author="Atlas",
        goal=p["goal_txt"],
        experience_min=Experience.BEGINNER,
        progression_family=p["family"],
        days_per_week=(2, 3, 4, 5, 6),
        split_by_days={d: list(s) for d, s in _COACH_SPLITS.items()},
        frequency_per_muscle="~2×/semana por grupo muscular",
        sets_per_exercise="3-4",
        reps=p["reps"],
        rir=p["rir"],
        rest_seconds=p["rest"],
        compound_ratio=p["ratio"],
        # Cada ocorrência de um foco repetido (ex.: "superior" 2x na semana)
        # escolhe exercício de novo — dá variação real (equipamento/ângulo
        # diferente) em vez de repetir a sessão idêntica.
        repeat_same_session=False,
        mesocycle_weeks="ciclos de ~6 semanas + deload conforme a periodização escolhida",
        deload_rule="Deload conduzido pela periodização do coach (automática/linear/ondulatória).",
        progression_rule=(
            "Sobrecarga progressiva: feche o topo da faixa de reps com técnica limpa, então suba a carga "
            "e volte à base da faixa. Reps primeiro, carga depois."
        ),
        coaching_notes=(
            "Compostos primeiro, isolados depois, em cada sessão.",
            "Frequência mínima de 2×/semana por grupo — sem bro-split.",
        ),
        guide_excerpt=(
            "Plano do coach: treino baseado em ciência, adaptado ao seu objetivo e à frequência que você "
            "escolheu (2 a 6 dias), com 2×/semana por grupo muscular, compostos antes de isolados e "
            "sobrecarga progressiva."
        ),
    )
