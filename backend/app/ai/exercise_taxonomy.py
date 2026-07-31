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


def order_class_for_pattern(pattern: Pattern | None) -> int:
    """Classe de ordem de um padrão. Padrão desconhecido/ausente conta como
    isolador — nunca como músculo menor, pra não parecer que pode fechar o
    treino sem ser."""
    if pattern is None:
        return ORDER_ISOLATION
    return _ORDER_BY_PATTERN.get(pattern, ORDER_ISOLATION)


# --- MECÂNICA do exercício (Caps. XI, XII e XV do manual de regras) --------
# Os três atributos acima (tier, padrão, região) respondem "qual exercício
# entra e em que ordem". Estes quatro respondem "COMO ele é executado": quantas
# repetições, com quanta folga pra falha e quanto descanso.
#
# Eram justamente os dados que faltavam. Sem eles a faixa de repetições era 8-12
# fixa pra tudo — do agachamento livre à elevação lateral —, o que o manual
# rejeita explicitamente: a faixa tem que ser consequência da estabilidade, do
# perfil de resistência, do risco articular e de quem encerra a série.


class Stability(str, Enum):
    """Quanto o exercício se sustenta sozinho (Cap. XI Parte C).

    É o atributo que mais manda na faixa e no RIR: trajetória guiada permite
    carga alta e ir perto da falha com segurança; exercício que exige equilíbrio
    perde a técnica antes do músculo cansar.
    """

    ALTA = "alta"      # máquina, polia, Smith: trajetória guiada, tronco apoiado
    MEDIA = "media"    # halteres e barra livres, com base estável
    BAIXA = "baixa"    # unilateral em pé, peso corporal suspenso, alta exigência técnica


class Resistance(str, Enum):
    """Onde a tensão mecânica é maior ao longo da amplitude (Caps. V e VI).

    O manual separa "perfil de resistência" e "comprimento muscular enfatizado",
    mas numa tabela os dois classificam a MESMA coisa e nunca discordariam —
    duas colunas que sempre concordam são uma coluna só. Ficou uma.
    """

    ALONGADO = "alongado"      # pico com o músculo esticado (Scott, terra romeno, crucifixo)
    MEIO = "meio"              # resistência distribuída (remada máquina, rosca na polia)
    ENCURTADO = "encurtado"    # pico na contração (elevação lateral, cadeira abdutora)


class Systemic(str, Enum):
    """Custo pro corpo inteiro — carga axial e demanda neural juntas.

    O manual as trata separadas. Nesta biblioteca elas andam coladas (o que
    comprime a coluna é o mesmo que exige o sistema nervoso: barra livre pesada),
    e separá-las criaria duas colunas idênticas pra revisar. Manda no DESCANSO e
    em quanto o exercício atrapalha o seguinte.
    """

    ALTO = "alto"      # barra livre com coluna carregada: agachamento, terra, stiff
    MEDIO = "medio"    # composto guiado ou halteres pesados
    BAIXO = "baixo"    # isolador e máquina com apoio


class JointRisk(str, Enum):
    """Custo articular com carga alta (Cap. XI Parte D). Risco alto empurra a
    faixa PRA CIMA: menos carga absoluta pelo mesmo estímulo."""

    ALTO = "alto"
    MEDIO = "medio"
    BAIXO = "baixo"


class Limiter(str, Enum):
    """Quem tende a encerrar a série (Cap. XI Parte B).

    "A série não deve ser considerada otimizada quando termina predominantemente
    por um fator que não contribui para o objetivo do exercício." Quando não é o
    músculo-alvo, a saída é encurtar a série — daí este atributo puxar a faixa
    PRA BAIXO, ao contrário do risco articular.
    """

    ALVO = "alvo"                    # o músculo que se quer treinar (o ideal)
    PEGADA = "pegada"                # antebraço solta antes: puxadas, remada livre
    LOMBAR = "lombar"                # eretores cedem antes: remada curvada, stiff
    ESTABILIZADORES = "estabilizadores"  # equilíbrio: búlgaro, afundo, prancha
    CARDIO = "cardio"                # falta de ar antes da falha muscular


@dataclass(frozen=True)
class Taxon:
    tier: Tier
    pattern: Pattern
    region: str
    # Sem padrão de propósito: são os dois que mais mudam a prescrição, e um
    # padrão silencioso seria um exercício novo recebendo faixa errada sem
    # ninguém notar. Assim, esquecer de declarar é erro na hora de importar.
    stability: Stability
    resistance: Resistance
    # Estes três têm padrão porque o caso comum da biblioteca (máquina isoladora,
    # limitada pelo próprio músculo) é de longe o mais frequente. Declarar só
    # quando FOGE do comum mantém a tabela legível.
    systemic: Systemic = Systemic.BAIXO
    joint_risk: JointRisk = JointRisk.BAIXO
    limiter: Limiter = Limiter.ALVO

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
St, Rs, Sy, Jr, Lm = Stability, Resistance, Systemic, JointRisk, Limiter

# Chave = nome EXATO em seed_exercises_curated.EXERCISES.
# Tiers vindos da lista do usuário (2026-07-30), sem reinterpretação.
#
# Colunas: tier, padrão, região, ESTABILIDADE, RESISTÊNCIA e — só quando fogem do
# comum — custo sistêmico, risco articular e quem encerra a série.
TAXONOMY: dict[str, Taxon] = {
    # --- Peito -------------------------------------------------------------
    # Todo empurrar horizontal tem pico de tensão embaixo (peito alongado); o que
    # os separa é a estabilidade. Barra livre soma custo sistêmico e risco de
    # ombro que a máquina não tem — é isso que vai dar faixas diferentes pra
    # exercícios que hoje recebem 8-12 igualzinho.
    "Supino inclinado no Smith": Taxon(T.S, P.PUSH_H, CLAVICULAR, St.ALTA, Rs.ALONGADO, systemic=Sy.MEDIO),
    "Chest press": Taxon(T.S, P.PUSH_H, ESTERNAL, St.ALTA, Rs.MEIO),
    "Supino inclinado máquina": Taxon(T.S, P.PUSH_H, CLAVICULAR, St.ALTA, Rs.ALONGADO),
    "Supino máquina": Taxon(T.S, P.PUSH_H, ESTERNAL, St.ALTA, Rs.MEIO),
    "Supino reto no Smith": Taxon(T.S, P.PUSH_H, ESTERNAL, St.ALTA, Rs.ALONGADO, systemic=Sy.MEDIO),
    "Peck deck": Taxon(T.S, P.ISO, ESTERNAL, St.ALTA, Rs.ALONGADO),
    "Supino inclinado com halteres": Taxon(T.A, P.PUSH_H, CLAVICULAR, St.MEDIA, Rs.ALONGADO, systemic=Sy.MEDIO),
    "Supino reto com halteres": Taxon(T.A, P.PUSH_H, ESTERNAL, St.MEDIA, Rs.ALONGADO, systemic=Sy.MEDIO),
    # Crossover: a polia BAIXA sobe (fibras claviculares); média e alta
    # trabalham a porção esternal. É o que faz "3 crossovers" não ser 3x a
    # mesma coisa — mas alta e média continuam sendo, e a regra pega isso.
    "Crossover na polia média": Taxon(T.A, P.ISO, ESTERNAL, St.ALTA, Rs.ALONGADO),
    "Crossover na polia baixa": Taxon(T.A, P.ISO, CLAVICULAR, St.ALTA, Rs.ALONGADO),
    "Crossover na polia alta": Taxon(T.A, P.ISO, ESTERNAL, St.ALTA, Rs.ALONGADO),
    "Supino reto com barra": Taxon(T.B, P.PUSH_H, ESTERNAL, St.MEDIA, Rs.ALONGADO,
                                   systemic=Sy.ALTO, joint_risk=Jr.MEDIO),
    "Supino inclinado com barra": Taxon(T.B, P.PUSH_H, CLAVICULAR, St.MEDIA, Rs.ALONGADO,
                                        systemic=Sy.ALTO, joint_risk=Jr.MEDIO),
    "Supino declinado no Smith": Taxon(T.B, P.PUSH_H, PEITO_INFERIOR, St.ALTA, Rs.MEIO, systemic=Sy.MEDIO),
    "Supino declinado com barra": Taxon(T.B, P.PUSH_H, PEITO_INFERIOR, St.MEDIA, Rs.MEIO, systemic=Sy.ALTO),
    # Crucifixo com halteres carrega o ombro justamente na posição alongada, que
    # é onde ele é mais vulnerável — daí risco médio mesmo sendo isolador.
    "Crucifixo inclinado com halteres": Taxon(T.B, P.ISO, CLAVICULAR, St.MEDIA, Rs.ALONGADO, joint_risk=Jr.MEDIO),
    "Crucifixo reto com halteres": Taxon(T.B, P.ISO, ESTERNAL, St.MEDIA, Rs.ALONGADO, joint_risk=Jr.MEDIO),
    "Flexão de braços": Taxon(T.C, P.PUSH_H, ESTERNAL, St.MEDIA, Rs.MEIO),
    # --- Costas ------------------------------------------------------------
    # Puxada e remada livre terminam pela PEGADA muito antes das costas — o
    # manual chama isso de série encerrada por fator que não é o objetivo. Marcar
    # aqui é o que faz o motor encurtar a série em vez de insistir.
    "Remada com peito apoiado": Taxon(T.S, P.PULL_H, UPPER_BACK, St.ALTA, Rs.ALONGADO),
    "Remada Hammer": Taxon(T.S, P.PULL_H, UPPER_BACK, St.ALTA, Rs.ALONGADO),
    "Remada articulada": Taxon(T.S, P.PULL_H, UPPER_BACK, St.ALTA, Rs.ALONGADO),
    "Remada máquina": Taxon(T.S, P.PULL_H, UPPER_BACK, St.ALTA, Rs.MEIO),
    "Remada baixa na polia": Taxon(T.S, P.PULL_H, UPPER_BACK, St.ALTA, Rs.MEIO),
    "Puxada frontal pegada neutra": Taxon(T.S, P.PULL_V, DORSAIS, St.ALTA, Rs.ALONGADO, limiter=Lm.PEGADA),
    "Pullover na máquina": Taxon(T.S, P.ISO, DORSAIS, St.ALTA, Rs.ALONGADO),
    "Puxada frontal pegada fechada": Taxon(T.A, P.PULL_V, DORSAIS, St.ALTA, Rs.ALONGADO, limiter=Lm.PEGADA),
    "Puxada frontal aberta": Taxon(T.A, P.PULL_V, DORSAIS, St.ALTA, Rs.ALONGADO, limiter=Lm.PEGADA),
    # Pulldown de braços estendidos e pullover são articulação ÚNICA (extensão
    # de ombro) — o classificador por palavra-chave marcava o pulldown como
    # composto por causa do "pulldown". A taxonomia corrige.
    "Pulldown com braços estendidos": Taxon(T.A, P.ISO, DORSAIS, St.ALTA, Rs.ALONGADO),
    "Pullover na polia": Taxon(T.A, P.ISO, DORSAIS, St.ALTA, Rs.ALONGADO),
    "Remada unilateral com halter": Taxon(T.A, P.PULL_H, UPPER_BACK, St.MEDIA, Rs.ALONGADO, limiter=Lm.PEGADA),
    "Remada com peito apoiado e halteres": Taxon(T.A, P.PULL_H, UPPER_BACK, St.ALTA, Rs.ALONGADO,
                                                 limiter=Lm.PEGADA),
    "Barra fixa supinada": Taxon(T.B, P.PULL_V, DORSAIS, St.BAIXA, Rs.ALONGADO,
                                 systemic=Sy.MEDIO, limiter=Lm.PEGADA),
    "Barra fixa pronada": Taxon(T.B, P.PULL_V, DORSAIS, St.BAIXA, Rs.ALONGADO,
                                systemic=Sy.MEDIO, limiter=Lm.PEGADA),
    "Remada cavalinho": Taxon(T.B, P.PULL_H, UPPER_BACK, St.MEDIA, Rs.MEIO,
                              systemic=Sy.MEDIO, limiter=Lm.LOMBAR),
    # Tier C com motivo declarado pelo usuário: a remada curvada é eficiente,
    # mas gera fadiga lombar demais pro estímulo que entrega quando existe
    # remada apoiada na base. É o mesmo motivo que a marca como limitada pela
    # lombar aqui — os dois atributos contam a mesma história.
    "Remada curvada com barra": Taxon(T.C, P.PULL_H, UPPER_BACK, St.BAIXA, Rs.MEIO,
                                      systemic=Sy.ALTO, limiter=Lm.LOMBAR),
    "Remada alta na máquina": Taxon(T.C, P.PULL_V, TRAPEZIO, St.ALTA, Rs.MEIO),
    # --- Ombros ------------------------------------------------------------
    # Elevação lateral e crucifixo inverso têm pico na CONTRAÇÃO e carga absoluta
    # baixa: é o caso que o manual manda levar pra 10-15, e sai disso sozinho.
    "Elevação lateral na máquina": Taxon(T.S, P.ISO, DELT_LATERAL, St.ALTA, Rs.ENCURTADO),
    "Elevação lateral na polia": Taxon(T.S, P.ISO, DELT_LATERAL, St.ALTA, Rs.ENCURTADO),
    "Desenvolvimento na máquina": Taxon(T.S, P.PUSH_V, DELT_ANTERIOR, St.ALTA, Rs.MEIO, systemic=Sy.MEDIO),
    "Desenvolvimento no Smith": Taxon(T.S, P.PUSH_V, DELT_ANTERIOR, St.ALTA, Rs.MEIO, systemic=Sy.MEDIO),
    "Crucifixo inverso na máquina": Taxon(T.S, P.ISO, DELT_POSTERIOR, St.ALTA, Rs.ENCURTADO),
    "Desenvolvimento com halteres": Taxon(T.A, P.PUSH_V, DELT_ANTERIOR, St.MEDIA, Rs.ALONGADO, systemic=Sy.MEDIO),
    "Desenvolvimento com barra": Taxon(T.A, P.PUSH_V, DELT_ANTERIOR, St.MEDIA, Rs.MEIO,
                                       systemic=Sy.ALTO, joint_risk=Jr.MEDIO),
    "Face pull": Taxon(T.A, P.ISO, DELT_POSTERIOR, St.ALTA, Rs.ENCURTADO),
    "Elevação lateral com halteres": Taxon(T.A, P.ISO, DELT_LATERAL, St.MEDIA, Rs.ENCURTADO),
    "Crucifixo inverso com halteres": Taxon(T.A, P.ISO, DELT_POSTERIOR, St.MEDIA, Rs.ENCURTADO),
    "Desenvolvimento Arnold": Taxon(T.B, P.PUSH_V, DELT_ANTERIOR, St.BAIXA, Rs.MEIO,
                                    systemic=Sy.MEDIO, joint_risk=Jr.MEDIO),
    "Elevação frontal na polia": Taxon(T.B, P.ISO, DELT_ANTERIOR, St.ALTA, Rs.MEIO),
    "Elevação frontal com halteres": Taxon(T.B, P.ISO, DELT_ANTERIOR, St.MEDIA, Rs.MEIO),
    # Ombros tier C na lista do usuário, mas o músculo PRIMÁRIO no nosso banco
    # é costas (mesma família da remada alta na máquina) — a região trapézio é
    # o que impede ela de ser considerada redundante com uma puxada.
    "Remada alta com barra": Taxon(T.C, P.PULL_V, TRAPEZIO, St.MEDIA, Rs.MEIO, joint_risk=Jr.MEDIO),
    # --- Bíceps ------------------------------------------------------------
    # Scott e inclinada põem o bíceps alongado (ombro atrás do tronco); rosca em
    # pé e martelo têm resistência bem distribuída.
    "Rosca Scott na máquina": Taxon(T.S, P.ISO, BICEPS_R, St.ALTA, Rs.ALONGADO),
    "Rosca na polia": Taxon(T.S, P.ISO, BICEPS_R, St.ALTA, Rs.MEIO),
    "Rosca inclinada com halteres": Taxon(T.S, P.ISO, BICEPS_R, St.MEDIA, Rs.ALONGADO),
    "Rosca Scott com barra": Taxon(T.S, P.ISO, BICEPS_R, St.MEDIA, Rs.ALONGADO, joint_risk=Jr.MEDIO),
    "Rosca alternada com halteres": Taxon(T.A, P.ISO, BICEPS_R, St.MEDIA, Rs.MEIO),
    "Rosca direta com barra W": Taxon(T.A, P.ISO, BICEPS_R, St.MEDIA, Rs.MEIO),
    "Rosca martelo": Taxon(T.A, P.ISO, BICEPS_R, St.MEDIA, Rs.MEIO),
    # Barra RETA fixa o punho em supinação forçada — é a queixa clássica de
    # cotovelo/punho, e por isso pede carga menor que a barra W.
    "Rosca direta com barra reta": Taxon(T.B, P.ISO, BICEPS_R, St.MEDIA, Rs.MEIO, joint_risk=Jr.MEDIO),
    "Rosca simultânea com halteres": Taxon(T.B, P.ISO, BICEPS_R, St.MEDIA, Rs.MEIO),
    "Rosca concentrada": Taxon(T.B, P.ISO, BICEPS_R, St.ALTA, Rs.MEIO),
    # --- Tríceps -----------------------------------------------------------
    # Acima da cabeça = cabeça longa alongada. Corda e barra na polia têm pico na
    # extensão (encurtado). Testa e francês castigam o cotovelo.
    "Tríceps máquina": Taxon(T.S, P.ISO, TRICEPS_GERAL, St.ALTA, Rs.MEIO),
    "Tríceps francês na polia": Taxon(T.S, P.ISO, TRICEPS_LONGA, St.ALTA, Rs.ALONGADO),
    # Polia mantém tensão parecida na amplitude toda — não é "pico na contração"
    # como a elevação lateral. A diferença importa: ENCURTADO empurraria estes
    # dois pra 10-15, e o manual pede 8-12 como referência de extensão de tríceps.
    "Tríceps corda": Taxon(T.S, P.ISO, TRICEPS_GERAL, St.ALTA, Rs.MEIO),
    "Tríceps na polia com barra": Taxon(T.S, P.ISO, TRICEPS_GERAL, St.ALTA, Rs.MEIO),
    "Tríceps francês com halter": Taxon(T.A, P.ISO, TRICEPS_LONGA, St.MEDIA, Rs.ALONGADO, joint_risk=Jr.MEDIO),
    "Tríceps testa com halteres": Taxon(T.A, P.ISO, TRICEPS_LONGA, St.MEDIA, Rs.ALONGADO, joint_risk=Jr.MEDIO),
    "Tríceps testa com barra": Taxon(T.A, P.ISO, TRICEPS_LONGA, St.MEDIA, Rs.ALONGADO, joint_risk=Jr.MEDIO),
    "Supino fechado": Taxon(T.B, P.PUSH_H, TRICEPS_GERAL, St.MEDIA, Rs.MEIO,
                            systemic=Sy.MEDIO, joint_risk=Jr.MEDIO),
    "Paralelas": Taxon(T.B, P.PUSH_V, TRICEPS_GERAL, St.BAIXA, Rs.ALONGADO,
                       systemic=Sy.MEDIO, joint_risk=Jr.MEDIO),
    "Tríceps coice": Taxon(T.C, P.ISO, TRICEPS_GERAL, St.MEDIA, Rs.ENCURTADO),
    # --- Quadríceps --------------------------------------------------------
    # Todo agachamento tem pico embaixo. O que muda é quem sustenta a carga: no
    # hack e no leg press a máquina sustenta; no livre, a coluna e o equilíbrio.
    "Hack squat": Taxon(T.S, P.KNEE, QUADRICEPS, St.ALTA, Rs.ALONGADO, systemic=Sy.MEDIO),
    "Agachamento pendular": Taxon(T.S, P.KNEE, QUADRICEPS, St.ALTA, Rs.ALONGADO, systemic=Sy.MEDIO),
    "Leg press 45°": Taxon(T.S, P.KNEE, QUADRICEPS, St.ALTA, Rs.ALONGADO, systemic=Sy.MEDIO),
    "Cadeira extensora": Taxon(T.S, P.ISO, QUADRICEPS, St.ALTA, Rs.MEIO, joint_risk=Jr.MEDIO),
    "Agachamento no Smith": Taxon(T.S, P.KNEE, QUADRICEPS, St.ALTA, Rs.ALONGADO, systemic=Sy.MEDIO),
    "Leg press horizontal": Taxon(T.A, P.KNEE, QUADRICEPS, St.ALTA, Rs.ALONGADO, systemic=Sy.MEDIO),
    # Frontal termina pelo tronco (upper back cede antes da perna), não pela coxa.
    "Agachamento frontal": Taxon(T.A, P.KNEE, QUADRICEPS, St.BAIXA, Rs.ALONGADO,
                                 systemic=Sy.ALTO, limiter=Lm.ESTABILIZADORES),
    "Afundo no Smith": Taxon(T.A, P.KNEE, QUADRICEPS, St.MEDIA, Rs.ALONGADO, systemic=Sy.MEDIO),
    # Série longa de agachamento livre acaba pela respiração, não pelo quadríceps.
    "Agachamento livre": Taxon(T.A, P.KNEE, QUADRICEPS, St.BAIXA, Rs.ALONGADO,
                               systemic=Sy.ALTO, joint_risk=Jr.MEDIO, limiter=Lm.CARDIO),
    "Afundo com halteres": Taxon(T.B, P.KNEE, QUADRICEPS, St.BAIXA, Rs.ALONGADO,
                                 systemic=Sy.MEDIO, limiter=Lm.ESTABILIZADORES),
    "Agachamento búlgaro": Taxon(T.B, P.KNEE, QUADRICEPS, St.BAIXA, Rs.ALONGADO,
                                 systemic=Sy.MEDIO, limiter=Lm.ESTABILIZADORES),
    "Passada com halteres": Taxon(T.B, P.KNEE, QUADRICEPS, St.BAIXA, Rs.ALONGADO,
                                  systemic=Sy.MEDIO, limiter=Lm.ESTABILIZADORES),
    # --- Adutores (seção própria na lista do usuário) ----------------------
    "Cadeira adutora": Taxon(T.S, P.ADDUCTION, ADUTORES, St.ALTA, Rs.ALONGADO),
    "Adução de quadril na polia": Taxon(T.A, P.ADDUCTION, ADUTORES, St.ALTA, Rs.MEIO),
    # --- Posterior e glúteos ----------------------------------------------
    # Flexora SENTADA deixa o posterior alongado (quadril fletido); a MESA
    # (deitada) tem resistência mais no meio. É a mesma lógica que já separa as
    # panturrilhas — e é o que faz as duas caberem na semana sem redundância.
    "Mesa flexora": Taxon(T.S, P.KNEE_FLEX, POST_FLEX_JOELHO, St.ALTA, Rs.MEIO),
    "Cadeira flexora": Taxon(T.S, P.KNEE_FLEX, POST_FLEX_JOELHO, St.ALTA, Rs.ALONGADO),
    # Elevação pélvica tem pico na CONTRAÇÃO (quadril estendido) — o oposto do
    # terra romeno, e por isso os dois se complementam em vez de competir.
    "Elevação pélvica na máquina": Taxon(T.S, P.HIP, GLUTEO_MAXIMO, St.ALTA, Rs.ENCURTADO),
    "Elevação pélvica no Smith": Taxon(T.S, P.HIP, GLUTEO_MAXIMO, St.ALTA, Rs.ENCURTADO),
    "Levantamento terra romeno": Taxon(T.S, P.HIP, POST_EXT_QUADRIL, St.MEDIA, Rs.ALONGADO,
                                       systemic=Sy.ALTO, limiter=Lm.LOMBAR),
    "Elevação pélvica com barra": Taxon(T.A, P.HIP, GLUTEO_MAXIMO, St.MEDIA, Rs.ENCURTADO),
    "Flexora em pé": Taxon(T.A, P.KNEE_FLEX, POST_FLEX_JOELHO, St.ALTA, Rs.MEIO),
    "Stiff com barra": Taxon(T.A, P.HIP, POST_EXT_QUADRIL, St.MEDIA, Rs.ALONGADO,
                             systemic=Sy.ALTO, limiter=Lm.LOMBAR),
    "Stiff com halteres": Taxon(T.A, P.HIP, POST_EXT_QUADRIL, St.MEDIA, Rs.ALONGADO,
                                systemic=Sy.MEDIO, limiter=Lm.LOMBAR),
    "Glúteo na máquina": Taxon(T.B, P.ISO, GLUTEO_MAXIMO, St.ALTA, Rs.ENCURTADO),
    "Glúteo na polia": Taxon(T.B, P.ISO, GLUTEO_MAXIMO, St.ALTA, Rs.ENCURTADO),
    "Good morning": Taxon(T.B, P.HIP, POST_EXT_QUADRIL, St.BAIXA, Rs.ALONGADO,
                          systemic=Sy.ALTO, joint_risk=Jr.MEDIO, limiter=Lm.LOMBAR),
    # Tier C com motivo do usuário: o terra tradicional é excelente pra força
    # geral, mas tem relação estímulo/fadiga inferior pra hipertrofia de
    # posterior quando existe terra romeno e flexora.
    "Levantamento terra tradicional": Taxon(T.C, P.HIP, POST_EXT_QUADRIL, St.BAIXA, Rs.MEIO,
                                            systemic=Sy.ALTO, joint_risk=Jr.MEDIO, limiter=Lm.LOMBAR),
    "Coice na máquina": Taxon(T.C, P.ISO, GLUTEO_MAXIMO, St.ALTA, Rs.ENCURTADO),
    "Cadeira abdutora": Taxon(T.S, P.ABDUCTION, GLUTEO_MEDIO, St.ALTA, Rs.ENCURTADO),
    "Abdução de quadril na polia": Taxon(T.A, P.ABDUCTION, GLUTEO_MEDIO, St.ALTA, Rs.ENCURTADO),
    # --- Panturrilhas ------------------------------------------------------
    # Sentada trabalha o sóleo (joelho flexionado); em pé/Smith/leg press
    # pegam o gastrocnêmio. Regiões diferentes = as duas cabem na mesma semana
    # sem serem redundantes, que é o correto. Todas com pico no alongamento,
    # que é onde a panturrilha realmente responde.
    "Panturrilha no Smith": Taxon(T.S, P.CALF, GASTROCNEMIO, St.ALTA, Rs.ALONGADO),
    "Panturrilha em pé": Taxon(T.S, P.CALF, GASTROCNEMIO, St.ALTA, Rs.ALONGADO),
    "Panturrilha sentada": Taxon(T.S, P.CALF, SOLEO, St.ALTA, Rs.ALONGADO),
    "Panturrilha unilateral": Taxon(T.A, P.CALF, GASTROCNEMIO, St.MEDIA, Rs.ALONGADO),
    "Panturrilha no leg press": Taxon(T.A, P.CALF, GASTROCNEMIO, St.ALTA, Rs.ALONGADO),
    # --- Abdômen / core ----------------------------------------------------
    "Abdominal na polia": Taxon(T.S, P.CORE, RETO_ABDOMINAL, St.ALTA, Rs.ENCURTADO),
    "Abdominal máquina": Taxon(T.S, P.CORE, RETO_ABDOMINAL, St.ALTA, Rs.ENCURTADO),
    "Elevação de pernas": Taxon(T.S, P.CORE, RETO_ABDOMINAL, St.MEDIA, Rs.ALONGADO),
    # "Reverse crunch" da lista do usuário é ESTE exercício (o pacote de
    # imagens trazia o mesmo GIF com os dois nomes, e o seed já unificava).
    # Fica com o tier S que ele deu ao movimento, não o B do nome duplicado.
    "Abdominal infra": Taxon(T.S, P.CORE, RETO_ABDOMINAL, St.MEDIA, Rs.MEIO),
    "Abdominal com roda": Taxon(T.S, P.CORE, CORE_ESTABILIDADE, St.BAIXA, Rs.ALONGADO,
                                limiter=Lm.ESTABILIZADORES),
    "Elevação de joelhos na barra": Taxon(T.A, P.CORE, RETO_ABDOMINAL, St.MEDIA, Rs.MEIO, limiter=Lm.PEGADA),
    "Abdominal supra": Taxon(T.A, P.CORE, RETO_ABDOMINAL, St.MEDIA, Rs.ENCURTADO),
    "Abdominal remador": Taxon(T.A, P.CORE, RETO_ABDOMINAL, St.MEDIA, Rs.MEIO),
    "Prancha abdominal": Taxon(T.A, P.CORE, CORE_ESTABILIDADE, St.ALTA, Rs.MEIO,
                               limiter=Lm.ESTABILIZADORES),
    "Dead bug": Taxon(T.A, P.CORE, CORE_ESTABILIDADE, St.ALTA, Rs.MEIO, limiter=Lm.ESTABILIZADORES),
    "Abdominal bicicleta": Taxon(T.B, P.CORE, OBLIQUOS, St.MEDIA, Rs.MEIO),
    "Abdominal oblíquo": Taxon(T.B, P.CORE, OBLIQUOS, St.MEDIA, Rs.ENCURTADO),
    "Prancha lateral": Taxon(T.B, P.CORE, OBLIQUOS, St.MEDIA, Rs.MEIO, limiter=Lm.ESTABILIZADORES),
    "Rotação russa": Taxon(T.B, P.CORE, OBLIQUOS, St.MEDIA, Rs.MEIO),
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
    # Mecânica CONSERVADORA pro exercício que a tabela não conhece (custom do
    # usuário, ou linha antiga viva numa rotina salva): estabilidade média e
    # resistência no meio levam a uma faixa central e a um RIR com folga. Um
    # exercício desconhecido não pode receber a prescrição agressiva que só faz
    # sentido pra quem a gente sabe que é guiado e seguro.
    return Taxon(Tier.B, padrao, regiao, Stability.MEDIA, Resistance.MEIO,
                 systemic=Systemic.MEDIO if is_compound else Systemic.BAIXO)


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
# Duas exclusões de propósito:
#
# - PEITO INFERIOR: a spec diz "fibras inferiores quando necessário" — é
#   opcional, então exigir reprovaria treino bom.
# - DELTOIDE ANTERIOR: a própria análise do usuário sobre o treino de
#   referência diz "apenas o deltoide lateral recebe trabalho direto, enquanto o
#   anterior é suficientemente estimulado pelos supinos". Cobrar trabalho direto
#   de anterior geraria elevação frontal (tier B) em treino que já tem 2 ou 3
#   empurradas — volume desperdiçado, exatamente o que o Princípio 4 combate.
REQUIRED_REGIONS: dict[MuscleGroup, tuple[str, ...]] = {
    MuscleGroup.CHEST: (CLAVICULAR, ESTERNAL),
    MuscleGroup.BACK: (DORSAIS, UPPER_BACK),
    MuscleGroup.SHOULDERS: (DELT_LATERAL, DELT_POSTERIOR),
    MuscleGroup.HAMSTRINGS: (POST_EXT_QUADRIL, POST_FLEX_JOELHO),
}
