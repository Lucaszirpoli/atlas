"""TAXONOMIA dos exercícios — o vocabulário da regra mestra de seleção.

O motor de treino antes só sabia duas coisas de cada exercício: qual músculo
principal ele treina e se é composto ou isolado. Com isso dá pra montar um
treino que "cobre os músculos", mas não dá pra cumprir a regra mestra, que
cobra decisões de outra natureza:

  - Princípio 2/regra de substituição: qual exercício é PRIMEIRA escolha
    (tier S) e qual só entra por um motivo (tier A/B/C).
  - Princípio 3: a ordem da sessão depende do PAPEL do exercício, não do
    músculo — "composto prioritário", depois "composto complementar", depois
    isoladores, e músculos menores no fim.
  - Princípio 4: dois exercícios não podem cumprir a mesma função. Supino reto
    barra + supino reto Smith + chest press são o mesmo PADRÃO na mesma REGIÃO;
    supino inclinado + chest press + peck deck não são.
  - Princípio 5: alternar padrões (empurrar -> puxar) pra distribuir fadiga.
  - Princípio 6: cobrir as REGIÕES de cada músculo na semana (clavicular e
    esternal do peito; dorsais e upper back das costas; os três deltoides;
    extensão de quadril e flexão de joelho do posterior).

Este módulo é só DADO — três atributos por exercício (tier, padrão de
movimento, região enfatizada). Quem decide com eles é o motor.

## Por que indexado por NOME e não por coluna no banco

A chave é o nome exato do exercício em `seed_exercises_curated.EXERCISES`, que
já é a chave estável do produto: o id inteiro muda de banco pra banco (dev x
produção), o nome não — é por isso que o seed faz upsert por nome. Colocar
tier/padrão/região como colunas custaria migração + ALTER cedo no init_db (a
lição do 502 de 2026-07-18), e não compraria nada: a biblioteca visível tem 119
exercícios, então o motor carrega todos numa consulta e resolve a taxonomia em
memória.

Exercício fora da tabela (criado pelo usuário, ou linha antiga escondida que
ainda vive numa rotina salva) NÃO quebra nada: `taxon_for` devolve um palpite
conservador a partir do músculo e do is_compound — ver `_fallback`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.core.text import normalize_search_text
from app.models.exercise import MuscleGroup


class Tier(str, Enum):
    """Prioridade de escolha (Princípio 2). Tier A/B/C NÃO é exercício ruim: é
    exercício cuja utilização depende de um motivo — ampliar amplitude, mudar o
    perfil de resistência, poupar articulação, acomodar equipamento."""

    S = "S"
    A = "A"
    B = "B"
    C = "C"


_TIER_RANK: dict[Tier, int] = {Tier.S: 0, Tier.A: 1, Tier.B: 2, Tier.C: 3}


def tier_rank(tier: Tier) -> int:
    """0 pra tier S ... 3 pra tier C — pra ordenar candidatos (menor = melhor)."""
    return _TIER_RANK[tier]


class Pattern(str, Enum):
    """Padrão de movimento. É a unidade que a regra mestra usa pra ordenar a
    sessão, alternar estímulos e detectar redundância."""

    PUSH_H = "empurrar_horizontal"
    PUSH_V = "empurrar_vertical"
    PULL_H = "puxar_horizontal"
    PULL_V = "puxar_vertical"
    KNEE = "dominante_joelho"
    HIP = "dominante_quadril"
    KNEE_FLEX = "flexao_joelho"
    ISO = "isolamento"
    CALF = "panturrilha"
    ABDUCTION = "abducao"
    ADDUCTION = "aducao"
    CORE = "core"


# Padrões multiarticulares. Esta é a definição de "composto" do motor — e é
# autoritativa sobre a coluna `Exercise.is_compound` (ver `sync_is_compound` no
# seed): a coluna vem de um classificador por palavra-chave que errava casos
# como o pulldown de braços estendidos, que é articulação única.
COMPOUND_PATTERNS: frozenset[Pattern] = frozenset(
    {Pattern.PUSH_H, Pattern.PUSH_V, Pattern.PULL_H, Pattern.PULL_V, Pattern.KNEE, Pattern.HIP}
)

# Padrões antagonistas/complementares (Princípio 5): depois de um, o motor
# prefere o outro pra distribuir a fadiga em vez de empilhar no mesmo grupo.
COMPLEMENT_OF: dict[Pattern, tuple[Pattern, ...]] = {
    Pattern.PUSH_H: (Pattern.PULL_H, Pattern.PULL_V),
    Pattern.PUSH_V: (Pattern.PULL_V, Pattern.PULL_H),
    Pattern.PULL_H: (Pattern.PUSH_H, Pattern.PUSH_V),
    Pattern.PULL_V: (Pattern.PUSH_V, Pattern.PUSH_H),
    Pattern.KNEE: (Pattern.HIP, Pattern.KNEE_FLEX),
    Pattern.HIP: (Pattern.KNEE,),
    Pattern.KNEE_FLEX: (Pattern.KNEE,),
}


# --- REGIÕES musculares (Princípio 6) --------------------------------------
# Só as regiões que a regra mestra nomeia explicitamente. Não inventar
# subdivisão que a spec não pede: região que ninguém cobre é volume fantasma.
CLAVICULAR = "peito clavicular"
ESTERNAL = "peito esternal"
PEITO_INFERIOR = "peito inferior"
DORSAIS = "dorsais"
UPPER_BACK = "upper back"
TRAPEZIO = "trapézio"
DELT_ANTERIOR = "deltoide anterior"
DELT_LATERAL = "deltoide lateral"
DELT_POSTERIOR = "deltoide posterior"
BICEPS_R = "bíceps"
TRICEPS_LONGA = "tríceps cabeça longa"
TRICEPS_GERAL = "tríceps"
QUADRICEPS = "quadríceps"
ADUTORES = "adutores"
POST_EXT_QUADRIL = "posterior (extensão de quadril)"
POST_FLEX_JOELHO = "posterior (flexão de joelho)"
GLUTEO_MAXIMO = "glúteo máximo"
GLUTEO_MEDIO = "glúteo médio"
GASTROCNEMIO = "panturrilha (gastrocnêmio)"
SOLEO = "panturrilha (sóleo)"
RETO_ABDOMINAL = "reto abdominal"
OBLIQUOS = "oblíquos"
CORE_ESTABILIDADE = "estabilidade de core"


# --- ORDEM na sessão (Princípio 3) -----------------------------------------
# A regra mestra tem 5 posições. As três primeiras são todas de COMPOSTO
# (composto prioritário -> composto complementar -> 2º estímulo do grupo
# prioritário), então elas não se distinguem por classe: quem as separa é o
# sequenciamento do motor. O que a classe separa é composto x isolador x
# músculo menor, que é o que nunca pode trocar de lugar.
ORDER_COMPOUND = 1  # posições 1-3 da regra mestra
ORDER_ISOLATION = 4  # "isoladores estratégicos"
ORDER_MINOR = 5  # "finalizar com músculos menores": panturrilha, abdutor/adutor, core

_ORDER_BY_PATTERN: dict[Pattern, int] = {
    Pattern.PUSH_H: ORDER_COMPOUND,
    Pattern.PUSH_V: ORDER_COMPOUND,
    Pattern.PULL_H: ORDER_COMPOUND,
    Pattern.PULL_V: ORDER_COMPOUND,
    Pattern.KNEE: ORDER_COMPOUND,
    Pattern.HIP: ORDER_COMPOUND,
    Pattern.KNEE_FLEX: ORDER_ISOLATION,
    Pattern.ISO: ORDER_ISOLATION,
    Pattern.CALF: ORDER_MINOR,
    Pattern.ABDUCTION: ORDER_MINOR,
    Pattern.ADDUCTION: ORDER_MINOR,
    Pattern.CORE: ORDER_MINOR,
}


@dataclass(frozen=True)
class Taxon:
    tier: Tier
    pattern: Pattern
    region: str

    @property
    def is_compound(self) -> bool:
        return self.pattern in COMPOUND_PATTERNS

    @property
    def order_class(self) -> int:
        return _ORDER_BY_PATTERN[self.pattern]

    @property
    def function_key(self) -> tuple[Pattern, str]:
        """A FUNÇÃO do exercício no treino (Princípio 4). Dois exercícios com a
        mesma função são redundantes entre si: supino reto barra, supino reto
        Smith e chest press são todos (empurrar horizontal, peito esternal).
        Supino inclinado (clavicular), chest press (esternal) e peck deck
        (isolamento) têm funções distintas — é a combinação que a spec elogia."""
        return (self.pattern, self.region)


T, P = Tier, Pattern

# Chave = nome EXATO em seed_exercises_curated.EXERCISES.
# Tiers vindos da lista do usuário (2026-07-30), sem reinterpretação.
TAXONOMY: dict[str, Taxon] = {
    # --- Peito -------------------------------------------------------------
    "Supino inclinado no Smith": Taxon(T.S, P.PUSH_H, CLAVICULAR),
    "Chest press": Taxon(T.S, P.PUSH_H, ESTERNAL),
    "Supino inclinado máquina": Taxon(T.S, P.PUSH_H, CLAVICULAR),
    "Supino máquina": Taxon(T.S, P.PUSH_H, ESTERNAL),
    "Supino reto no Smith": Taxon(T.S, P.PUSH_H, ESTERNAL),
    "Peck deck": Taxon(T.S, P.ISO, ESTERNAL),
    "Supino inclinado com halteres": Taxon(T.A, P.PUSH_H, CLAVICULAR),
    "Supino reto com halteres": Taxon(T.A, P.PUSH_H, ESTERNAL),
    # Crossover: a polia BAIXA sobe (fibras claviculares); média e alta
    # trabalham a porção esternal. É o que faz "3 crossovers" não ser 3x a
    # mesma coisa — mas alta e média continuam sendo, e a regra pega isso.
    "Crossover na polia média": Taxon(T.A, P.ISO, ESTERNAL),
    "Crossover na polia baixa": Taxon(T.A, P.ISO, CLAVICULAR),
    "Crossover na polia alta": Taxon(T.A, P.ISO, ESTERNAL),
    "Supino reto com barra": Taxon(T.B, P.PUSH_H, ESTERNAL),
    "Supino inclinado com barra": Taxon(T.B, P.PUSH_H, CLAVICULAR),
    "Supino declinado no Smith": Taxon(T.B, P.PUSH_H, PEITO_INFERIOR),
    "Supino declinado com barra": Taxon(T.B, P.PUSH_H, PEITO_INFERIOR),
    "Crucifixo inclinado com halteres": Taxon(T.B, P.ISO, CLAVICULAR),
    "Crucifixo reto com halteres": Taxon(T.B, P.ISO, ESTERNAL),
    "Flexão de braços": Taxon(T.C, P.PUSH_H, ESTERNAL),
    # --- Costas ------------------------------------------------------------
    "Remada com peito apoiado": Taxon(T.S, P.PULL_H, UPPER_BACK),
    "Remada Hammer": Taxon(T.S, P.PULL_H, UPPER_BACK),
    "Remada articulada": Taxon(T.S, P.PULL_H, UPPER_BACK),
    "Remada máquina": Taxon(T.S, P.PULL_H, UPPER_BACK),
    "Remada baixa na polia": Taxon(T.S, P.PULL_H, UPPER_BACK),
    "Puxada frontal pegada neutra": Taxon(T.S, P.PULL_V, DORSAIS),
    "Pullover na máquina": Taxon(T.S, P.ISO, DORSAIS),
    "Puxada frontal pegada fechada": Taxon(T.A, P.PULL_V, DORSAIS),
    "Puxada frontal aberta": Taxon(T.A, P.PULL_V, DORSAIS),
    # Pulldown de braços estendidos e pullover são articulação ÚNICA (extensão
    # de ombro) — o classificador por palavra-chave marcava o pulldown como
    # composto por causa do "pulldown". A taxonomia corrige.
    "Pulldown com braços estendidos": Taxon(T.A, P.ISO, DORSAIS),
    "Pullover na polia": Taxon(T.A, P.ISO, DORSAIS),
    "Remada unilateral com halter": Taxon(T.A, P.PULL_H, UPPER_BACK),
    "Remada com peito apoiado e halteres": Taxon(T.A, P.PULL_H, UPPER_BACK),
    "Barra fixa supinada": Taxon(T.B, P.PULL_V, DORSAIS),
    "Barra fixa pronada": Taxon(T.B, P.PULL_V, DORSAIS),
    "Remada cavalinho": Taxon(T.B, P.PULL_H, UPPER_BACK),
    # Tier C com motivo declarado pelo usuário: a remada curvada é eficiente,
    # mas gera fadiga lombar demais pro estímulo que entrega quando existe
    # remada apoiada na base.
    "Remada curvada com barra": Taxon(T.C, P.PULL_H, UPPER_BACK),
    "Remada alta na máquina": Taxon(T.C, P.PULL_V, TRAPEZIO),
    # --- Ombros ------------------------------------------------------------
    "Elevação lateral na máquina": Taxon(T.S, P.ISO, DELT_LATERAL),
    "Elevação lateral na polia": Taxon(T.S, P.ISO, DELT_LATERAL),
    "Desenvolvimento na máquina": Taxon(T.S, P.PUSH_V, DELT_ANTERIOR),
    "Desenvolvimento no Smith": Taxon(T.S, P.PUSH_V, DELT_ANTERIOR),
    "Crucifixo inverso na máquina": Taxon(T.S, P.ISO, DELT_POSTERIOR),
    "Desenvolvimento com halteres": Taxon(T.A, P.PUSH_V, DELT_ANTERIOR),
    "Desenvolvimento com barra": Taxon(T.A, P.PUSH_V, DELT_ANTERIOR),
    "Face pull": Taxon(T.A, P.ISO, DELT_POSTERIOR),
    "Elevação lateral com halteres": Taxon(T.A, P.ISO, DELT_LATERAL),
    "Crucifixo inverso com halteres": Taxon(T.A, P.ISO, DELT_POSTERIOR),
    "Desenvolvimento Arnold": Taxon(T.B, P.PUSH_V, DELT_ANTERIOR),
    "Elevação frontal na polia": Taxon(T.B, P.ISO, DELT_ANTERIOR),
    "Elevação frontal com halteres": Taxon(T.B, P.ISO, DELT_ANTERIOR),
    # Ombros tier C na lista do usuário, mas o músculo PRIMÁRIO no nosso banco
    # é costas (mesma família da remada alta na máquina) — a região trapézio é
    # o que impede ela de ser considerada redundante com uma puxada.
    "Remada alta com barra": Taxon(T.C, P.PULL_V, TRAPEZIO),
    # --- Bíceps ------------------------------------------------------------
    "Rosca Scott na máquina": Taxon(T.S, P.ISO, BICEPS_R),
    "Rosca na polia": Taxon(T.S, P.ISO, BICEPS_R),
    "Rosca inclinada com halteres": Taxon(T.S, P.ISO, BICEPS_R),
    "Rosca Scott com barra": Taxon(T.S, P.ISO, BICEPS_R),
    "Rosca alternada com halteres": Taxon(T.A, P.ISO, BICEPS_R),
    "Rosca direta com barra W": Taxon(T.A, P.ISO, BICEPS_R),
    "Rosca martelo": Taxon(T.A, P.ISO, BICEPS_R),
    "Rosca direta com barra reta": Taxon(T.B, P.ISO, BICEPS_R),
    "Rosca simultânea com halteres": Taxon(T.B, P.ISO, BICEPS_R),
    "Rosca concentrada": Taxon(T.B, P.ISO, BICEPS_R),
    # --- Tríceps -----------------------------------------------------------
    "Tríceps máquina": Taxon(T.S, P.ISO, TRICEPS_GERAL),
    "Tríceps francês na polia": Taxon(T.S, P.ISO, TRICEPS_LONGA),
    "Tríceps corda": Taxon(T.S, P.ISO, TRICEPS_GERAL),
    "Tríceps na polia com barra": Taxon(T.S, P.ISO, TRICEPS_GERAL),
    "Tríceps francês com halter": Taxon(T.A, P.ISO, TRICEPS_LONGA),
    "Tríceps testa com halteres": Taxon(T.A, P.ISO, TRICEPS_LONGA),
    "Tríceps testa com barra": Taxon(T.A, P.ISO, TRICEPS_LONGA),
    "Supino fechado": Taxon(T.B, P.PUSH_H, TRICEPS_GERAL),
    "Paralelas": Taxon(T.B, P.PUSH_V, TRICEPS_GERAL),
    "Tríceps coice": Taxon(T.C, P.ISO, TRICEPS_GERAL),
    # --- Quadríceps --------------------------------------------------------
    "Hack squat": Taxon(T.S, P.KNEE, QUADRICEPS),
    "Agachamento pendular": Taxon(T.S, P.KNEE, QUADRICEPS),
    "Leg press 45°": Taxon(T.S, P.KNEE, QUADRICEPS),
    "Cadeira extensora": Taxon(T.S, P.ISO, QUADRICEPS),
    "Agachamento no Smith": Taxon(T.S, P.KNEE, QUADRICEPS),
    "Leg press horizontal": Taxon(T.A, P.KNEE, QUADRICEPS),
    "Agachamento frontal": Taxon(T.A, P.KNEE, QUADRICEPS),
    "Afundo no Smith": Taxon(T.A, P.KNEE, QUADRICEPS),
    "Agachamento livre": Taxon(T.A, P.KNEE, QUADRICEPS),
    "Afundo com halteres": Taxon(T.B, P.KNEE, QUADRICEPS),
    "Agachamento búlgaro": Taxon(T.B, P.KNEE, QUADRICEPS),
    "Passada com halteres": Taxon(T.B, P.KNEE, QUADRICEPS),
    # --- Adutores (seção própria na lista do usuário) ----------------------
    "Cadeira adutora": Taxon(T.S, P.ADDUCTION, ADUTORES),
    "Adução de quadril na polia": Taxon(T.A, P.ADDUCTION, ADUTORES),
    # --- Posterior e glúteos ----------------------------------------------
    "Mesa flexora": Taxon(T.S, P.KNEE_FLEX, POST_FLEX_JOELHO),
    "Cadeira flexora": Taxon(T.S, P.KNEE_FLEX, POST_FLEX_JOELHO),
    "Elevação pélvica na máquina": Taxon(T.S, P.HIP, GLUTEO_MAXIMO),
    "Elevação pélvica no Smith": Taxon(T.S, P.HIP, GLUTEO_MAXIMO),
    "Levantamento terra romeno": Taxon(T.S, P.HIP, POST_EXT_QUADRIL),
    "Elevação pélvica com barra": Taxon(T.A, P.HIP, GLUTEO_MAXIMO),
    "Flexora em pé": Taxon(T.A, P.KNEE_FLEX, POST_FLEX_JOELHO),
    "Stiff com barra": Taxon(T.A, P.HIP, POST_EXT_QUADRIL),
    "Stiff com halteres": Taxon(T.A, P.HIP, POST_EXT_QUADRIL),
    "Glúteo na máquina": Taxon(T.B, P.ISO, GLUTEO_MAXIMO),
    "Glúteo na polia": Taxon(T.B, P.ISO, GLUTEO_MAXIMO),
    "Good morning": Taxon(T.B, P.HIP, POST_EXT_QUADRIL),
    # Tier C com motivo do usuário: o terra tradicional é excelente pra força
    # geral, mas tem relação estímulo/fadiga inferior pra hipertrofia de
    # posterior quando existe terra romeno e flexora.
    "Levantamento terra tradicional": Taxon(T.C, P.HIP, POST_EXT_QUADRIL),
    "Coice na máquina": Taxon(T.C, P.ISO, GLUTEO_MAXIMO),
    "Cadeira abdutora": Taxon(T.S, P.ABDUCTION, GLUTEO_MEDIO),
    "Abdução de quadril na polia": Taxon(T.A, P.ABDUCTION, GLUTEO_MEDIO),
    # --- Panturrilhas ------------------------------------------------------
    # Sentada trabalha o sóleo (joelho flexionado); em pé/Smith/leg press
    # pegam o gastrocnêmio. Regiões diferentes = as duas cabem na mesma semana
    # sem serem redundantes, que é o correto.
    "Panturrilha no Smith": Taxon(T.S, P.CALF, GASTROCNEMIO),
    "Panturrilha em pé": Taxon(T.S, P.CALF, GASTROCNEMIO),
    "Panturrilha sentada": Taxon(T.S, P.CALF, SOLEO),
    "Panturrilha unilateral": Taxon(T.A, P.CALF, GASTROCNEMIO),
    "Panturrilha no leg press": Taxon(T.A, P.CALF, GASTROCNEMIO),
    # --- Abdômen / core ----------------------------------------------------
    "Abdominal na polia": Taxon(T.S, P.CORE, RETO_ABDOMINAL),
    "Abdominal máquina": Taxon(T.S, P.CORE, RETO_ABDOMINAL),
    "Elevação de pernas": Taxon(T.S, P.CORE, RETO_ABDOMINAL),
    # "Reverse crunch" da lista do usuário é ESTE exercício (o pacote de
    # imagens trazia o mesmo GIF com os dois nomes, e o seed já unificava).
    # Fica com o tier S que ele deu ao movimento, não o B do nome duplicado.
    "Abdominal infra": Taxon(T.S, P.CORE, RETO_ABDOMINAL),
    "Abdominal com roda": Taxon(T.S, P.CORE, CORE_ESTABILIDADE),
    "Elevação de joelhos na barra": Taxon(T.A, P.CORE, RETO_ABDOMINAL),
    "Abdominal supra": Taxon(T.A, P.CORE, RETO_ABDOMINAL),
    "Abdominal remador": Taxon(T.A, P.CORE, RETO_ABDOMINAL),
    "Prancha abdominal": Taxon(T.A, P.CORE, CORE_ESTABILIDADE),
    "Dead bug": Taxon(T.A, P.CORE, CORE_ESTABILIDADE),
    "Abdominal bicicleta": Taxon(T.B, P.CORE, OBLIQUOS),
    "Abdominal oblíquo": Taxon(T.B, P.CORE, OBLIQUOS),
    "Prancha lateral": Taxon(T.B, P.CORE, OBLIQUOS),
    "Rotação russa": Taxon(T.B, P.CORE, OBLIQUOS),
}


# Índice normalizado (sem acento/caixa) — o nome que chega do banco pode ter
# vindo de um upsert antigo com acentuação diferente.
_BY_NORM: dict[str, Taxon] = {normalize_search_text(k): v for k, v in TAXONOMY.items()}


# Fallback por músculo pra exercício fora da tabela (custom do usuário, ou
# linha escondida que ainda vive numa rotina antiga). Tier B: nunca é primeira
# escolha do motor, mas também não é descartado.
_FALLBACK_COMPOUND: dict[MuscleGroup, tuple[Pattern, str]] = {
    MuscleGroup.CHEST: (Pattern.PUSH_H, ESTERNAL),
    MuscleGroup.BACK: (Pattern.PULL_H, UPPER_BACK),
    MuscleGroup.SHOULDERS: (Pattern.PUSH_V, DELT_ANTERIOR),
    MuscleGroup.QUADS: (Pattern.KNEE, QUADRICEPS),
    MuscleGroup.HAMSTRINGS: (Pattern.HIP, POST_EXT_QUADRIL),
    MuscleGroup.GLUTES: (Pattern.HIP, GLUTEO_MAXIMO),
    MuscleGroup.TRICEPS: (Pattern.PUSH_H, TRICEPS_GERAL),
    MuscleGroup.BICEPS: (Pattern.PULL_H, BICEPS_R),
}
_FALLBACK_ISO: dict[MuscleGroup, tuple[Pattern, str]] = {
    MuscleGroup.CHEST: (Pattern.ISO, ESTERNAL),
    MuscleGroup.BACK: (Pattern.ISO, DORSAIS),
    MuscleGroup.SHOULDERS: (Pattern.ISO, DELT_LATERAL),
    MuscleGroup.BICEPS: (Pattern.ISO, BICEPS_R),
    MuscleGroup.TRICEPS: (Pattern.ISO, TRICEPS_GERAL),
    MuscleGroup.QUADS: (Pattern.ISO, QUADRICEPS),
    MuscleGroup.HAMSTRINGS: (Pattern.KNEE_FLEX, POST_FLEX_JOELHO),
    MuscleGroup.GLUTES: (Pattern.ISO, GLUTEO_MAXIMO),
    MuscleGroup.CALVES: (Pattern.CALF, GASTROCNEMIO),
    MuscleGroup.ABS: (Pattern.CORE, RETO_ABDOMINAL),
    MuscleGroup.TRAPS: (Pattern.ISO, TRAPEZIO),
    MuscleGroup.FOREARMS: (Pattern.ISO, BICEPS_R),
}


def _fallback(muscle: MuscleGroup | None, is_compound: bool) -> Taxon:
    tabela = _FALLBACK_COMPOUND if is_compound else _FALLBACK_ISO
    padrao, regiao = tabela.get(
        muscle or MuscleGroup.FULL_BODY,
        (Pattern.PUSH_H, ESTERNAL) if is_compound else (Pattern.ISO, ESTERNAL),
    )
    return Taxon(Tier.B, padrao, regiao)


def taxon_for(name: str, muscle: MuscleGroup | None = None, is_compound: bool = False) -> Taxon:
    """A taxonomia de um exercício pelo nome. Nunca levanta: exercício fora da
    tabela recebe um palpite conservador (tier B) a partir do músculo — o motor
    continua funcionando com exercício custom, só não o promove a 1ª escolha."""
    direto = TAXONOMY.get(name)
    if direto is not None:
        return direto
    norm = _BY_NORM.get(normalize_search_text(name or ""))
    if norm is not None:
        return norm
    return _fallback(muscle, is_compound)


def taxon_for_exercise(exercise) -> Taxon:
    """Atalho pra um `Exercise` do ORM."""
    return taxon_for(
        exercise.name,
        exercise.primary_muscle_group,
        bool(getattr(exercise, "is_compound", False)),
    )


def is_known(name: str) -> bool:
    return name in TAXONOMY or normalize_search_text(name or "") in _BY_NORM


# --- Cobertura regional exigida por músculo (Princípio 6) ------------------
# "Não basta trabalhar um músculo": estas são as regiões que a SEMANA precisa
# cobrir quando o músculo é treinado. O validador global cobra isto.
#
# Peito inferior fica FORA de propósito: a spec diz "fibras inferiores quando
# necessário" — é opcional, então exigi-lo reprovaria treino bom.
REQUIRED_REGIONS: dict[MuscleGroup, tuple[str, ...]] = {
    MuscleGroup.CHEST: (CLAVICULAR, ESTERNAL),
    MuscleGroup.BACK: (DORSAIS, UPPER_BACK),
    MuscleGroup.SHOULDERS: (DELT_ANTERIOR, DELT_LATERAL, DELT_POSTERIOR),
    MuscleGroup.HAMSTRINGS: (POST_EXT_QUADRIL, POST_FLEX_JOELHO),
}
