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
sessão é curta: 1 nunca cai, 2 cai antes de 3 — nunca o composto prioritário.

`priority` sozinho NÃO decide o corte, e essa distinção custou caro: por ela, a
vaga do fim do treino cai sempre, e a vaga do fim é panturrilha nos dois dias de
inferior e abdômen/tríceps nos dois de superior. Cada corte parecia certo olhando
o dia, e a semana saía sem uma única panturrilha e sem um único abdominal. Quem
decide o corte é `fit_week_to_target`, que olha a SEMANA e não deixa nenhum
músculo chegar a zero — a prioridade é só a ordem da fila dentro do que é
seguro cortar.
"""

from __future__ import annotations

from collections import Counter
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
    REQUIRED_REGIONS,
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
    # Abdômen no dia de INFERIOR, e não uma segunda vaga no de superior. O
    # volume semanal de abdômen pede 2 exercícios, e com abdômen só no
    # `superior a` os dois caíam no MESMO dia (abdominal máquina + abdominal com
    # roda um atrás do outro) — `add_accessory_slot` só acrescenta em dia que já
    # treina o músculo. O dia de superior ia a 8 exercícios enquanto o de
    # inferior ficava com 5. Aqui o par nasce em dias diferentes.
    _minor(P.CORE, M.ABS, priority=3),
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
    cortadas: set[int] = set()
    for i in _fila_de_corte(blueprint):
        if len(blueprint) - len(cortadas) <= alvo:
            break
        if i == 0 or i in protegidas:
            continue  # o composto prioritário e todo ponto fraco nunca saem
        cortadas.add(i)
    return [s for i, s in enumerate(blueprint) if i not in cortadas]


def _fila_de_corte(blueprint: list[SlotSpec]) -> list[int]:
    """Índices na ordem em que as vagas caem quando falta tempo.

    -priority: prioridade alta (3) primeiro. -i: dentro do mesmo nível, a vaga
    mais ao fim do treino sai antes — é a que a pessoa já ia cortar por cansaço.
    """
    return sorted(range(len(blueprint)), key=lambda i: (-blueprint[i].priority, -i))


# Piso de frequência semanal por músculo (regra 6 do produto: nada de bro-split,
# mínimo 2×/semana por grupo). O corte por tempo respeita este piso enquanto
# houver outra vaga que possa sair no lugar — ver `fit_week_to_target`.
FREQUENCIA_MINIMA_SEMANAL = 2

# ABDÔMEN é a exceção, e por mecânica, não por descaso: o core trabalha
# isometricamente em TODO composto em pé ou com carga axial (agachamento, terra,
# desenvolvimento, remada), então a frequência DIRETA dele pode ser menor sem que
# o estímulo da semana caia junto. Piso 1 = ele nunca some da semana, que era o
# bug; mas a SEGUNDA vaga de abdômen cede a vez quando o tempo aperta, em vez de
# empurrar pra fora uma elevação lateral — que não tem de onde vir indiretamente.
_PISO_PROPRIO: dict[MuscleGroup, int] = {MuscleGroup.ABS: 1}

# Quanto empurrar e puxar podem se afastar na semana antes de virar treino torto.
# É o mesmo número de `plan_review.TOLERANCIA_EQUILIBRIO` — repetido aqui em vez
# de importado porque `plan_review` já importa este módulo, e o corte precisa
# saber o efeito de tirar uma vaga ANTES de tirar, não depois de o validador
# reprovar.
_TOLERANCIA_EQUILIBRIO = 2


def _direcao_da_vaga(vaga: SlotSpec) -> str | None:
    """'empurrar', 'puxar' ou None — a mesma regra de `plan_review._direcao`,
    aplicada à VAGA (que ainda não tem exercício) em vez de ao slot montado.

    Braços e deltoide lateral ficam fora da conta de propósito: recebem tanto
    volume indireto que contá-los faria a soma responder por eles, e não pelo
    tronco — que é o que a pergunta quer saber.
    """
    if vaga.muscle is MuscleGroup.CHEST:
        return "empurrar"
    if vaga.muscle is MuscleGroup.BACK:
        return "puxar"
    if vaga.muscle is MuscleGroup.SHOULDERS:
        if vaga.pattern is Pattern.PUSH_V:
            return "empurrar"
        if vaga.region == DELT_POSTERIOR:
            return "puxar"
    return None


def fit_week_to_target(
    blueprints: list[list[SlotSpec]],
    target: int | None,
    *,
    protegidas_por_dia: list[frozenset[int]] | None = None,
) -> list[list[SlotSpec]]:
    """Recorta a SEMANA INTEIRA pro nº-alvo de exercícios por sessão.

    Por que a semana e não cada sessão: o corte é por SESSÃO, mas o estrago é na
    SEMANA. `fit_to_target` decide sozinha, olhando só o dia, e o que ela corta é
    sempre a vaga do fim — que no upper/lower é panturrilha nos DOIS dias de
    inferior, e tríceps nos DOIS de superior. Cada corte era defensável olhando o
    dia; o resultado era um treino de 4 dias sem uma única panturrilha, sem um
    único abdominal e sem um único tríceps direto na semana, no tempo "Médio",
    que é o padrão. E nada reclamava: `plan_review` só cobra região de músculo
    que o treino treina, e músculo com zero vaga não é treinado.

    A regra nova é uma só: **o corte por tempo não zera um músculo da semana**.
    O piso é o da regra 6 (2×/semana), limitado ao que o desenho já dava — um
    músculo que aparece 1× na divisão escolhida tem piso 1, não 2, porque o corte
    não pode ser cobrado por uma vaga que nunca existiu.

    Quando o alvo não cabe respeitando o piso, ele CEDE em degraus, e nunca o
    alvo: tempo é restrição física, e entregar 8 exercícios pra quem tem tempo de
    5 só faz a pessoa não terminar o treino. Os degraus, do mais pro menos
    exigente:

      0. 2×/semana por músculo E toda região exigida da semana preservada
      1. 2×/semana por músculo (região exigida pode cair)
      2. 1×/semana por músculo — o músculo não some, mas perde frequência
      3. sem piso — o alvo tem que ser atingido

    A região cede antes da frequência de propósito: 2×/semana é regra de produto,
    e uma região que se perde aqui ainda é recuperada depois pelo reparo de
    cobertura (`workout_builder._reparar_cobertura`), que sabe pedir exatamente a
    região faltante. Frequência perdida ninguém repõe.

    O corte é em rodízio (um por dia por vez), não um dia inteiro de cada vez:
    servindo um dia até o fim, ele consome sozinho todo o excedente de um músculo
    e o último dia fica sem corte legal nenhum, o que forçaria os degraus a ceder
    sem precisar.
    """
    if target is None:
        return [list(b) for b in blueprints]

    protegidas = list(protegidas_por_dia or [])
    protegidas += [frozenset()] * (len(blueprints) - len(protegidas))
    alvo = max(1, target)

    contagem: Counter[MuscleGroup] = Counter(v.muscle for b in blueprints for v in b)
    # O piso de um músculo é o da regra 6, LIMITADO ao que o desenho já dava: um
    # músculo que aparece 1× na divisão escolhida tem piso 1, não 2 — o corte não
    # pode ser cobrado por uma vaga que nunca existiu.
    piso = {
        m: min(_PISO_PROPRIO.get(m, FREQUENCIA_MINIMA_SEMANAL), n)
        for m, n in contagem.items()
    }

    # As regiões que a semana é OBRIGADA a cobrir (Princípio 6): peito clavicular
    # e esternal, costas dorsais e upper back, deltoide lateral e posterior,
    # posterior de coxa nas duas funções. Sem isto, o corte tirava a única
    # elevação lateral da semana só porque ombro ainda ficava com 2 vagas —
    # desenvolvimento e crucifixo inverso, nenhum dos dois lateral.
    exigidas = {(m, r) for m, regioes in REQUIRED_REGIONS.items() for r in regioes}
    regioes: Counter[tuple[MuscleGroup, str]] = Counter(
        (v.muscle, v.region) for b in blueprints for v in b if (v.muscle, v.region) in exigidas
    )

    # Os dois EQUILÍBRIOS que o validador cobra da semana, mantidos durante o
    # corte. Sem eles, o corte escolhia pelo piso de músculo — que é cego pra
    # direção do movimento — e tirava dois peitos e nenhuma costa (peito tem 3
    # vagas, costas 4), ou uma dominante de joelho e nenhuma de quadril. A semana
    # ficava coerente pela frequência e reprovada pelo `plan_review` logo depois.
    def _empurrar_puxar(vaga: SlotSpec) -> int:
        direcao = _direcao_da_vaga(vaga)
        return 1 if direcao == "empurrar" else -1 if direcao == "puxar" else 0

    def _joelho_quadril(vaga: SlotSpec) -> int:
        return 1 if vaga.pattern is P.KNEE else -1 if vaga.pattern is P.HIP else 0

    # A flexão de joelho fica FORA da conta joelho×quadril, como em
    # `plan_review.desequilibrio_joelho_quadril`: mesa flexora é trabalho de
    # posterior, mas não é dominância de quadril.
    _EQUILIBRIOS = (_empurrar_puxar, _joelho_quadril)
    saldos = [sum(f(v) for b in blueprints for v in b) for f in _EQUILIBRIOS]

    filas = [_fila_de_corte(b) for b in blueprints]
    cortadas: list[set[int]] = [set() for _ in blueprints]
    faltam = [max(0, len(b) - alvo) for b in blueprints]

    def pode_cortar(vaga: SlotSpec, degrau: int) -> bool:
        if degrau <= 1 and contagem[vaga.muscle] - 1 < piso[vaga.muscle]:
            return False
        if degrau == 2 and contagem[vaga.muscle] - 1 < 1:
            return False
        if degrau == 0 and regioes.get((vaga.muscle, vaga.region), 0) == 1:
            return False
        # Região e equilíbrio cedem juntos (degrau 2 em diante): os dois são
        # estrutura, e frequência mínima por músculo vem antes dos dois.
        if degrau <= 1 and any(
            abs(saldo - f(vaga)) >= _TOLERANCIA_EQUILIBRIO
            for saldo, f in zip(saldos, _EQUILIBRIOS)
        ):
            return False
        return True

    for degrau in range(4):
        while any(faltam):
            cortou_nesta_rodada = False
            for d, blueprint in enumerate(blueprints):
                if not faltam[d]:
                    continue
                for i in filas[d]:
                    # A vaga que ABRE o dia e todo ponto fraco marcado seguem
                    # intocáveis, como em `fit_to_target`.
                    if i == 0 or i in protegidas[d] or i in cortadas[d]:
                        continue
                    vaga = blueprint[i]
                    if not pode_cortar(vaga, degrau):
                        continue
                    cortadas[d].add(i)
                    contagem[vaga.muscle] -= 1
                    if (vaga.muscle, vaga.region) in regioes:
                        regioes[(vaga.muscle, vaga.region)] -= 1
                    saldos = [s - f(vaga) for s, f in zip(saldos, _EQUILIBRIOS)]
                    faltam[d] -= 1
                    cortou_nesta_rodada = True
                    break
            if not cortou_nesta_rodada:
                break  # nada mais sai neste degrau; o laço de fora afrouxa
        if not any(faltam):
            break

    return [
        [s for i, s in enumerate(b) if i not in cortadas[d]]
        for d, b in enumerate(blueprints)
    ]
