"""BLUEPRINTS de sessão — a regra mestra do Princípio 3 em forma de dados.

O motor antigo montava a sessão assim: pega os músculos do dia, calcula quantas
vagas são de composto e quantas de isolado, e preenche em rodízio entre os
músculos. Isso cobre os músculos, mas não constrói um SISTEMA: não garante que
depois de um empurrar venha um puxar, não sabe distinguir "segundo estímulo do
grupo prioritário" de "isolador estratégico", e não tem como evitar dois
exercícios com a mesma função.

Aqui cada dia é uma sequência EXPLÍCITA de vagas, e cada vaga declara o papel
que cumpre, o padrão de movimento aceito, o músculo e (quando importa) a região.
O motor só escolhe QUAL exercício entra em cada vaga — sempre o de tier mais
alto que não repete uma função já usada no dia.

Os dois blueprints de "superior a" e "inferior a" são transcrição direta dos
treinos de referência que o usuário passou como template (UPPER A / LOWER A),
inclusive na ordem. Os demais seguem a mesma lógica, variando padrão e região
pra fechar a cobertura semanal do Princípio 6.

Ordem das vagas = ordem no treino. `priority` só decide quem CAI quando a
sessão é curta: 1 nunca cai, 2 cai antes de 3. É por isso que numa sessão curta
o que sai é panturrilha/abdutor/core, e nunca o composto prioritário.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.exercise_taxonomy import (
    ADUTORES,
    CLAVICULAR,
    DELT_LATERAL,
    DELT_POSTERIOR,
    DORSAIS,
    ESTERNAL,
    GLUTEO_MAXIMO,
    GLUTEO_MEDIO,
    POST_EXT_QUADRIL,
    POST_FLEX_JOELHO,
    Pattern,
    UPPER_BACK,
)
from app.models.exercise import MuscleGroup

M = MuscleGroup
P = Pattern

# Papéis, na linguagem da regra mestra. Viram texto no app (nota da vaga), então
# são frases que a pessoa entende, não jargão interno.
ROLE_PRIMARY = "composto prioritário"
ROLE_COMPLEMENT = "composto complementar"
ROLE_SECOND = "segundo estímulo do grupo prioritário"
ROLE_ISO = "isolador estratégico"
ROLE_MINOR = "músculo menor"
ROLE_PRIORITY_OPEN = "prioridade — abre o treino descansado"


@dataclass(frozen=True)
class SlotSpec:
    """Uma vaga do treino: o papel, e o que pode preenchê-la."""

    role: str
    pattern: Pattern
    muscle: MuscleGroup
    # Região exigida (Princípio 6). None = qualquer região daquele músculo.
    region: str | None = None
    # 1 = essencial (nunca sai); 2 e 3 saem primeiro quando a sessão é curta.
    priority: int = 1
    # Quando True, esta vaga aceita repetir uma FUNÇÃO (padrão+região) já usada
    # no dia. Existe pros músculos pequenos, onde a biblioteca inteira cumpre a
    # mesma função: duas roscas num dia de pull não são redundância de verdade,
    # são volume de bíceps. Nos compostos fica False — é exatamente ali que a
    # redundância desperdiça volume (os 3 supinos retos do Princípio 4).
    allow_repeat_function: bool = False
    # Vaga que abre a sessão POR PRIORIDADE, e não por ser o movimento mais
    # pesado do dia. É a exceção consciente à regra "a sessão abre com composto"
    # (`plan_review.problemas_de_ordem`): quando o músculo prioritário não tem
    # composto próprio — braço é o caso — abrir com o isolador dele é o preço da
    # priorização, e o validador precisa saber que foi de propósito.
    opener: bool = False


def _iso(muscle: MuscleGroup, region: str | None = None, priority: int = 1, repeat: bool = False) -> SlotSpec:
    return SlotSpec(ROLE_ISO, P.ISO, muscle, region, priority, repeat)


def _abre(muscle: MuscleGroup, region: str | None = None) -> SlotSpec:
    """Isolador que ABRE a sessão por prioridade (ver `SlotSpec.opener`)."""
    return SlotSpec(ROLE_PRIORITY_OPEN, P.ISO, muscle, region, priority=1, opener=True)


def _second(pattern: Pattern, muscle: MuscleGroup, region: str | None = None) -> SlotSpec:
    """A vaga de "segundo estímulo para o grupo prioritário" (3ª posição da
    regra mestra).

    Ela SEMPRE aceita repetir função, e isso não é exceção à regra da
    não-redundância — é o que a spec pede literalmente: "Chest Press após Supino
    Inclinado. Leg Press após Hack Squat. Remada após Puxada." No peito os dois
    saem em regiões diferentes (clavicular e esternal), então nem precisariam da
    permissão; no quadríceps não existe distinção de região, e sem ela a vaga
    ficava VAZIA — o dia de inferior saía com 6 exercícios em vez de 7, sem
    ninguém perceber.

    O que impede isto de virar os três supinos retos do Princípio 4 é haver no
    máximo uma vaga dessas por sessão, mais o teto de 2 do `plan_review`.
    """
    return SlotSpec(ROLE_SECOND, pattern, muscle, region, priority=1, allow_repeat_function=True)


def _minor(pattern: Pattern, muscle: MuscleGroup, region: str | None = None, priority: int = 2) -> SlotSpec:
    return SlotSpec(ROLE_MINOR, pattern, muscle, region, priority)


# ---------------------------------------------------------------------------
# SUPERIOR / INFERIOR (A e B) — o split de 4 dias
# ---------------------------------------------------------------------------
# "Upper A: prioridade em movimentos horizontais. Upper B: maior ênfase em
# movimentos verticais e variações que complementem a sessão A."
#
# Cobertura da semana com A+B: peito clavicular (A) e esternal (A,B); costas
# upper back (A,B) e dorsais (A,B); deltoide lateral (A) e posterior (B) — o
# anterior vem dos supinos e desenvolvimentos, como a própria análise do
# usuário diz ("o anterior é suficientemente estimulado pelos supinos").
SUPERIOR_A: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.PUSH_H, M.CHEST, CLAVICULAR),
    SlotSpec(ROLE_COMPLEMENT, P.PULL_H, M.BACK, UPPER_BACK),
    _second(P.PUSH_H, M.CHEST, ESTERNAL),
    SlotSpec(ROLE_COMPLEMENT, P.PULL_V, M.BACK, DORSAIS),
    _iso(M.SHOULDERS, DELT_LATERAL),
    _iso(M.TRICEPS, priority=2),
    _iso(M.BICEPS, priority=2),
    _minor(P.CORE, M.ABS, priority=3),
]

SUPERIOR_B: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.PUSH_V, M.SHOULDERS),
    SlotSpec(ROLE_COMPLEMENT, P.PULL_V, M.BACK, DORSAIS),
    _second(P.PUSH_H, M.CHEST, ESTERNAL),
    SlotSpec(ROLE_COMPLEMENT, P.PULL_H, M.BACK, UPPER_BACK),
    _iso(M.SHOULDERS, DELT_POSTERIOR),
    _iso(M.BICEPS, priority=2),
    _iso(M.TRICEPS, priority=2),
]

# "Lower A: ênfase dominante de joelho. Lower B: ênfase dominante de quadril.
# Ambos mantêm equilíbrio entre quadríceps, posteriores, glúteos e panturrilhas."
INFERIOR_A: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.KNEE, M.QUADS),
    SlotSpec(ROLE_COMPLEMENT, P.HIP, M.HAMSTRINGS, POST_EXT_QUADRIL),
    _second(P.KNEE, M.QUADS),
    SlotSpec(ROLE_ISO, P.KNEE_FLEX, M.HAMSTRINGS, POST_FLEX_JOELHO),
    SlotSpec(ROLE_COMPLEMENT, P.HIP, M.GLUTES, GLUTEO_MAXIMO),
    _minor(P.ABDUCTION, M.GLUTES, GLUTEO_MEDIO),
    _minor(P.CALF, M.CALVES),
]

INFERIOR_B: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.HIP, M.HAMSTRINGS, POST_EXT_QUADRIL),
    SlotSpec(ROLE_COMPLEMENT, P.KNEE, M.QUADS),
    _second(P.HIP, M.GLUTES, GLUTEO_MAXIMO),
    SlotSpec(ROLE_ISO, P.KNEE_FLEX, M.HAMSTRINGS, POST_FLEX_JOELHO),
    _iso(M.QUADS),
    _minor(P.ADDUCTION, M.QUADS, ADUTORES),
    _minor(P.CALF, M.CALVES),
]

# ---------------------------------------------------------------------------
# PUSH / PULL / PERNAS — 6 dias (2 passagens) e parte do 5 dias
# ---------------------------------------------------------------------------
# "Na segunda passagem semanal, utilizar variações que alterem o perfil de
# resistência ou o vetor de força, evitando repetir exatamente os mesmos
# exercícios." A ordem A/B troca qual padrão lidera; a exclusão de exercício já
# usado na semana (no motor) garante que não sejam os mesmos.
PUSH_A: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.PUSH_H, M.CHEST, CLAVICULAR),
    SlotSpec(ROLE_COMPLEMENT, P.PUSH_V, M.SHOULDERS),
    _second(P.PUSH_H, M.CHEST, ESTERNAL),
    _iso(M.CHEST),
    _iso(M.SHOULDERS, DELT_LATERAL),
    _iso(M.TRICEPS),
    _iso(M.TRICEPS, priority=2, repeat=True),
]

PUSH_B: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.PUSH_H, M.CHEST, ESTERNAL),
    SlotSpec(ROLE_COMPLEMENT, P.PUSH_V, M.SHOULDERS),
    _second(P.PUSH_H, M.CHEST, CLAVICULAR),
    _iso(M.SHOULDERS, DELT_LATERAL),
    _iso(M.CHEST),
    _iso(M.TRICEPS),
    _iso(M.TRICEPS, priority=2, repeat=True),
]

# Costas fecham 3 funções distintas por dia: puxada vertical (dorsais), remada
# horizontal (upper back) e um straight-arm (pullover/pulldown, isolamento de
# dorsais). É o que permite 3 exercícios de costas no mesmo dia sem cair na
# redundância do Princípio 4.
PULL_A: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.PULL_V, M.BACK, DORSAIS),
    SlotSpec(ROLE_COMPLEMENT, P.PULL_H, M.BACK, UPPER_BACK),
    _iso(M.BACK, DORSAIS),
    _iso(M.SHOULDERS, DELT_POSTERIOR),
    _iso(M.BICEPS),
    _iso(M.BICEPS, priority=2, repeat=True),
    _minor(P.CORE, M.ABS, priority=3),
]

PULL_B: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.PULL_H, M.BACK, UPPER_BACK),
    SlotSpec(ROLE_COMPLEMENT, P.PULL_V, M.BACK, DORSAIS),
    _iso(M.BACK, DORSAIS),
    _iso(M.SHOULDERS, DELT_POSTERIOR),
    _iso(M.BICEPS),
    _iso(M.BICEPS, priority=2, repeat=True),
    _minor(P.CORE, M.ABS, priority=3),
]

# ---------------------------------------------------------------------------
# FULL BODY — 2 e 3 dias
# ---------------------------------------------------------------------------
# "Cada sessão deve conter: um movimento dominante de joelho; um dominante de
# quadril; um empurrar; uma puxada; um isolamento estratégico; panturrilhas ou
# core conforme necessidade."
#
# A e B sozinhos (2 dias) já fecham peito clavicular+esternal, costas
# dorsais+upper back, deltoide lateral+posterior e posterior de coxa nas duas
# funções (extensão de quadril e flexão de joelho). C é o terceiro dia e
# acrescenta glúteo direto e quadríceps isolado.
FULL_BODY_A: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.KNEE, M.QUADS),
    SlotSpec(ROLE_COMPLEMENT, P.PUSH_H, M.CHEST, CLAVICULAR),
    SlotSpec(ROLE_COMPLEMENT, P.PULL_H, M.BACK, UPPER_BACK),
    SlotSpec(ROLE_COMPLEMENT, P.HIP, M.HAMSTRINGS, POST_EXT_QUADRIL),
    _iso(M.SHOULDERS, DELT_LATERAL),
    _iso(M.TRICEPS, priority=2),
    _minor(P.CALF, M.CALVES, priority=3),
]

FULL_BODY_B: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.HIP, M.HAMSTRINGS, POST_EXT_QUADRIL),
    SlotSpec(ROLE_COMPLEMENT, P.PULL_V, M.BACK, DORSAIS),
    SlotSpec(ROLE_COMPLEMENT, P.PUSH_H, M.CHEST, ESTERNAL),
    SlotSpec(ROLE_COMPLEMENT, P.KNEE, M.QUADS),
    _iso(M.SHOULDERS, DELT_POSTERIOR),
    _iso(M.BICEPS, priority=2),
    SlotSpec(ROLE_ISO, P.KNEE_FLEX, M.HAMSTRINGS, POST_FLEX_JOELHO, priority=3),
    _minor(P.CORE, M.ABS, priority=3),
]

FULL_BODY_C: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.KNEE, M.QUADS),
    SlotSpec(ROLE_COMPLEMENT, P.PUSH_V, M.SHOULDERS),
    SlotSpec(ROLE_COMPLEMENT, P.PULL_H, M.BACK, UPPER_BACK),
    SlotSpec(ROLE_COMPLEMENT, P.HIP, M.GLUTES, GLUTEO_MAXIMO),
    _iso(M.QUADS),
    _iso(M.TRICEPS, priority=2, repeat=True),
    _minor(P.CALF, M.CALVES, priority=3),
]

# ---------------------------------------------------------------------------
# TORSO / MEMBROS — alternativa de 4 dias
# ---------------------------------------------------------------------------
# "Torso reúne todos os movimentos de membros superiores com equilíbrio entre
# empurrar e puxar. Limbs organiza quadríceps, posteriores, glúteos,
# panturrilhas e braços, permitindo maior volume para músculos menores sem
# sobrecarregar as sessões de tronco."
#
# É por isso que o coach só troca pra esta divisão quando o ponto fraco é braço
# ou panturrilha: fora desse caso ela não compra nada sobre upper/lower.
TORSO_A: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.PUSH_H, M.CHEST, CLAVICULAR),
    SlotSpec(ROLE_COMPLEMENT, P.PULL_H, M.BACK, UPPER_BACK),
    _second(P.PUSH_V, M.SHOULDERS),
    SlotSpec(ROLE_COMPLEMENT, P.PULL_V, M.BACK, DORSAIS),
    _iso(M.CHEST, ESTERNAL),
    _iso(M.SHOULDERS, DELT_LATERAL),
    _iso(M.SHOULDERS, DELT_POSTERIOR, priority=2),
    _minor(P.CORE, M.ABS, priority=3),
]

TORSO_B: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.PULL_H, M.BACK, UPPER_BACK),
    SlotSpec(ROLE_COMPLEMENT, P.PUSH_H, M.CHEST, ESTERNAL),
    _second(P.PULL_V, M.BACK, DORSAIS),
    SlotSpec(ROLE_COMPLEMENT, P.PUSH_V, M.SHOULDERS),
    _iso(M.BACK, DORSAIS),
    _iso(M.SHOULDERS, DELT_LATERAL),
    _iso(M.CHEST, CLAVICULAR, priority=2),
]

# O BRAÇO ABRE O DIA DE MEMBROS. A divisão Torso/Limbs só é escolhida quando o
# ponto fraco é justamente um músculo menor (braço ou panturrilha) — ela existe
# pra "permitir maior volume para músculos menores". Deixar o braço no fim, atrás
# de agachamento e levantamento terra, entrega justamente o contrário: a pessoa
# chega no motivo do dia já fatigada, e o volume prioritário sai pior que o
# volume que não é prioridade nenhuma.
#
# Abrir com isolador é exceção à regra "a sessão abre com composto", e é por isso
# que estas vagas são `opener=True` (ver `SlotSpec.opener`): o validador aceita a
# abertura porque ela é uma decisão de priorização, não um blueprint torto.
#
# Panturrilha e abdutor continuam nas ÚLTIMAS posições — músculo menor fecha o
# treino, e o validador cobra isso.
MEMBROS_A: list[SlotSpec] = [
    _abre(M.BICEPS),
    _abre(M.TRICEPS),
    SlotSpec(ROLE_PRIMARY, P.KNEE, M.QUADS),
    SlotSpec(ROLE_COMPLEMENT, P.HIP, M.HAMSTRINGS, POST_EXT_QUADRIL),
    SlotSpec(ROLE_ISO, P.KNEE_FLEX, M.HAMSTRINGS, POST_FLEX_JOELHO),
    _iso(M.BICEPS, priority=2, repeat=True),
    _iso(M.TRICEPS, priority=3, repeat=True),
    _minor(P.CALF, M.CALVES),
]

MEMBROS_B: list[SlotSpec] = [
    _abre(M.TRICEPS),
    _abre(M.BICEPS),
    SlotSpec(ROLE_PRIMARY, P.KNEE, M.QUADS),
    SlotSpec(ROLE_COMPLEMENT, P.HIP, M.GLUTES, GLUTEO_MAXIMO),
    _iso(M.QUADS),
    _iso(M.TRICEPS, priority=2, repeat=True),
    _minor(P.CALF, M.CALVES),
    _minor(P.ABDUCTION, M.GLUTES, GLUTEO_MEDIO, priority=3),
]

# ---------------------------------------------------------------------------
# SUPERIOR / INFERIOR "cheios" — os 2 dias extras do split de 5 (PPL + UL)
# ---------------------------------------------------------------------------
# "Os dias de Upper e Lower devem complementar os estímulos dos dias de Push,
# Pull e Legs, preenchendo lacunas de volume." Por isso estes dois são
# equilibrados (empurrar E puxar no mesmo dia) em vez de repetir a ênfase de um
# dia de push ou de pull.
SUPERIOR_CHEIO: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.PULL_H, M.BACK, UPPER_BACK),
    SlotSpec(ROLE_COMPLEMENT, P.PUSH_H, M.CHEST, CLAVICULAR),
    _second(P.PULL_V, M.BACK, DORSAIS),
    SlotSpec(ROLE_COMPLEMENT, P.PUSH_V, M.SHOULDERS),
    _iso(M.SHOULDERS, DELT_LATERAL),
    _iso(M.BICEPS, priority=2),
    _iso(M.TRICEPS, priority=2),
]

INFERIOR_CHEIO: list[SlotSpec] = [
    SlotSpec(ROLE_PRIMARY, P.HIP, M.HAMSTRINGS, POST_EXT_QUADRIL),
    SlotSpec(ROLE_COMPLEMENT, P.KNEE, M.QUADS),
    _second(P.HIP, M.GLUTES, GLUTEO_MAXIMO),
    SlotSpec(ROLE_ISO, P.KNEE_FLEX, M.HAMSTRINGS, POST_FLEX_JOELHO),
    _iso(M.QUADS),
    _minor(P.CALF, M.CALVES),
    _minor(P.ABDUCTION, M.GLUTES, GLUTEO_MEDIO, priority=3),
]


# Rótulo do foco -> blueprint. Os rótulos são os mesmos que os splits usam.
BLUEPRINTS: dict[str, list[SlotSpec]] = {
    "superior a": SUPERIOR_A,
    "superior b": SUPERIOR_B,
    "inferior a": INFERIOR_A,
    "inferior b": INFERIOR_B,
    "superior": SUPERIOR_CHEIO,
    "inferior": INFERIOR_CHEIO,
    "push a": PUSH_A,
    "push b": PUSH_B,
    "pull a": PULL_A,
    "pull b": PULL_B,
    "pernas a": INFERIOR_A,
    "pernas b": INFERIOR_B,
    "full body a": FULL_BODY_A,
    "full body b": FULL_BODY_B,
    "full body c": FULL_BODY_C,
    "torso a": TORSO_A,
    "torso b": TORSO_B,
    "membros a": MEMBROS_A,
    "membros b": MEMBROS_B,
}


def blueprint_for(focus: str) -> list[SlotSpec]:
    """Blueprint do foco. Foco desconhecido cai em full body A — que é o desenho
    mais completo que existe, então um rótulo novo nunca gera treino quebrado."""
    return BLUEPRINTS.get(focus, FULL_BODY_A)


def fit_to_target(
    blueprint: list[SlotSpec], target: int | None, *, protegidas: frozenset[int] = frozenset()
) -> list[SlotSpec]:
    """Recorta o blueprint pro nº-alvo de exercícios da sessão (tempo disponível).

    Ordem do corte: primeiro as vagas de MAIOR `priority` (3, depois 2, depois
    1) e, dentro da mesma prioridade, as que estão mais perto do FIM do treino —
    que são as que a pessoa já ia cortar por cansaço.

    A vaga 1 (quem ABRE o treino) nunca sai — seja o composto prioritário (a
    maioria dos dias) ou a vaga de prioridade do dia de membros. `protegidas`
    estende essa garantia a outros índices específicos: é assim que TODO ponto
    fraco marcado sobrevive ao corte, não só o que ganhou a abertura do dia. Só
    um músculo pode abrir (é uma vaga só), mas a pessoa pode marcar até 2 pontos
    fracos — sem proteger os dois, o segundo "perdia" pro primeiro e era cortado
    do mesmo jeito que se ninguém o tivesse marcado.
    Fora de `protegidas` e da vaga 0, as de `priority=1` são as últimas a cair,
    mas caem se o alvo for menor que o número delas — o tempo é uma restrição
    física, e entregar 7 exercícios pra quem tem tempo de 5 só faz a pessoa não
    terminar o treino. Nesse caso o que sobra é o começo do treino, que é a
    escolha certa.

    Alvo maior que o blueprint não acrescenta vaga aqui: quem faz o treino
    crescer é o volume semanal (workout_builder.add_accessory_slot), que sabe
    QUAL músculo está devendo série.
    """
    if target is None or target >= len(blueprint):
        return list(blueprint)
    alvo = max(1, target)
    # -priority: prioridade alta (3) primeiro. -i: dentro do mesmo nível, a vaga
    # mais ao fim do treino sai antes.
    fila_de_corte = sorted(range(len(blueprint)), key=lambda i: (-blueprint[i].priority, -i))
    cortadas: set[int] = set()
    for i in fila_de_corte:
        if len(blueprint) - len(cortadas) <= alvo:
            break
        if i == 0 or i in protegidas:
            continue  # o composto prioritário e todo ponto fraco nunca saem
        cortadas.add(i)
    return [s for i, s in enumerate(blueprint) if i not in cortadas]
