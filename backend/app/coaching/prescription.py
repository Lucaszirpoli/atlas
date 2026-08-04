"""COMO cada exercício é executado: faixa de repetições, RIR-alvo e descanso.

Traduz os capítulos XI (faixas de repetições), XII (proximidade da falha) e XV
(descanso) do manual de regras em decisão determinística.

## O que muda em relação ao que existia

Antes o coach usava **8-12 repetições pra tudo** (`methods._COACH_REPS`) e um
descanso por OBJETIVO (90-120s pra hipertrofia, 60-90s pra emagrecimento). Ou
seja: agachamento livre e elevação lateral recebiam a mesma faixa, e o que
decidia o descanso era a meta da pessoa em vez do custo do exercício.

O manual rejeita as duas coisas explicitamente. A faixa tem que ser consequência
da estabilidade, do perfil de resistência, do risco articular e de quem encerra a
série; o descanso, do custo real do movimento.

## Por que a conta é por FAIXAS e não por fórmula

As faixas do manual são degraus (4-8, 5-9, 6-10, 8-12, 10-15), não um contínuo.
Modelar como escada de índices deixa cada regra do manual virar um "+1" ou "-1"
legível e testável, em vez de uma fórmula que ninguém consegue conferir.

O teto de 15 repetições é regra dura do manual e é o último degrau da escada —
não existe caminho pra passar dele.
"""

from __future__ import annotations

from app.ai.exercise_taxonomy import (
    JointRisk,
    Limiter,
    Resistance,
    Stability,
    Systemic,
    Taxon,
)

# A escada de faixas do Cap. XI, do mais pesado pro mais leve. Nenhuma passa de
# 15 repetições: "a engine não deve utilizar faixas superiores a 15 repetições".
REP_BANDS: list[tuple[int, int]] = [(4, 8), (5, 9), (6, 10), (8, 12), (10, 15)]

# Onde cada tipo de exercício COMEÇA na escada.
#
# Composto fica em 6-10 e isolador em 8-12 — as duas faixas que o manual chama de
# "geral". Estabilidade baixa não empurra pra faixa mais baixa nem mais alta: o
# manual diz que exercício instável deve evitar tanto o extremo baixo (risco
# técnico) quanto séries longas demais (a técnica degrada sob fadiga), então ele
# fica no meio e quem o ajusta são os modificadores.
_BASE_COMPOUND = 2   # (6, 10)
_BASE_ISOLATION = 3  # (8, 12)


def _clamp_band(i: int) -> int:
    return max(0, min(len(REP_BANDS) - 1, i))


def rep_band(taxon: Taxon, *, load_preference: str | None = None) -> tuple[int, int]:
    """A faixa de repetições do exercício (Cap. XI).

    Os modificadores, e o motivo de cada um:

    - **resistência no ENCURTADO -> +1.** Pico de tensão na contração vem junto
      com carga absoluta baixa e braço de alavanca longo (elevação lateral é o
      caso-modelo). Insistir em carga alta aí compra impulso, não estímulo.
    - **risco articular ALTO -> +1.** Faixa mais alta é como o manual manda
      reduzir carga absoluta sem perder tensão no músculo-alvo.
    - **série encerrada por LOMBAR ou CARDIO -> -1.** "A série não deve ser
      considerada otimizada quando termina predominantemente por um fator que não
      contribui para o objetivo": a saída é encurtar a série, não alongá-la.
      Pegada e estabilizadores NÃO entram aqui — eles não melhoram com série
      curta, e o manual os trata ajustando RIR e suporte, não a faixa.
    - **preferência da pessoa -> ±1.** É a única entrada subjetiva, e ela nunca
      atropela as anteriores: só desloca o resultado em um degrau.
    """
    i = _BASE_COMPOUND if taxon.is_compound else _BASE_ISOLATION

    if taxon.resistance is Resistance.ENCURTADO:
        i += 1
    if taxon.joint_risk is JointRisk.ALTO:
        i += 1
    if taxon.limiter in (Limiter.LOMBAR, Limiter.CARDIO):
        i -= 1

    if load_preference == "pesado":
        i -= 1
    elif load_preference == "leve":
        i += 1

    return REP_BANDS[_clamp_band(i)]


# --- RIR (Cap. XII) --------------------------------------------------------
# O RIR-alvo é quanta folga a série deixa. Menor = mais perto da falha.
RIR_MIN = 0
RIR_MAX = 3

# Piso de segurança: exercício instável ou de alto custo sistêmico NUNCA recebe
# alvo abaixo de 2, nem na última série, nem pra quem adora treinar no limite.
# "A possibilidade de realizar uma série até a falha com segurança não significa
# que essa estratégia possua boa relação estímulo/fadiga."
_RIR_FLOOR_ARRISCADO = 2


def target_rir(
    taxon: Taxon,
    *,
    experience: str | None = None,
    rir_accuracy: str | None = None,
    failure_comfort: str | None = None,
    is_last_set: bool = False,
) -> int:
    """O RIR-alvo de uma série (Cap. XII).

    Repare que ele depende da POSIÇÃO da série: o manual é explícito em que as
    séries iniciais preservam desempenho e as finais podem chegar mais perto da
    falha. Prescrever o mesmo RIR pras três séries ignora a fadiga acumulada.

    `rir_accuracy` é o que a pessoa respondeu sobre saber estimar repetições em
    reserva. Quem não sabe estimar recebe margem maior — o manual diz que a
    precisão do RIR "deve ser construída e validada, não presumida", então o
    motor não pode apostar num número que a pessoa não consegue enxergar.
    """
    arriscado = taxon.stability is Stability.BAIXA or taxon.systemic is Systemic.ALTO

    if taxon.stability is Stability.BAIXA:
        rir = 3
    elif taxon.stability is Stability.MEDIA or taxon.joint_risk is not JointRisk.BAIXO:
        rir = 2
    else:
        rir = 1

    if taxon.systemic is Systemic.ALTO:
        rir += 1
    # Quando quem encerra a série não é o músculo-alvo, o RIR relatado não
    # descreve o músculo — descreve a pegada, a lombar ou o fôlego. Margem maior.
    if taxon.limiter is not Limiter.ALVO:
        rir += 1

    if rir_accuracy == "nao":
        rir += 1
    if experience == "iniciante":
        rir += 1

    if failure_comfort == "evito":
        rir += 1
    elif failure_comfort == "sim":
        rir -= 1

    # A última série do exercício é a que pode fechar mais perto da falha: não há
    # série seguinte pra proteger.
    if is_last_set:
        rir -= 1

    rir = max(RIR_MIN, min(RIR_MAX, rir))
    if arriscado:
        rir = max(rir, _RIR_FLOOR_ARRISCADO)
    return rir


# --- Descanso (Cap. XV) ----------------------------------------------------
# Referências do manual: grandes compostos 2-4 min; compostos guiados 90-180s;
# máquinas e isoladores 60-120s. Os valores abaixo são o ponto de partida de cada
# classe — o ajuste fino vem dos modificadores.
_REST_COMPOUND_BY_SYSTEMIC: dict[Systemic, int] = {
    Systemic.ALTO: 180,
    Systemic.MEDIO: 150,
    Systemic.BAIXO: 120,
}
_REST_ISOLATION = 90
_REST_MINOR = 60

REST_MIN = 45
REST_MAX = 240


def rest_seconds(
    taxon: Taxon,
    *,
    goal: str | None = None,
    limitations: list[str] | None = None,
) -> int:
    """O descanso entre séries (Cap. XV).

    **Mudança de comportamento em relação ao que existia:** o descanso era
    definido pelo OBJETIVO (90-120s pra hipertrofia, 60-90s pra emagrecimento).
    Agora ele nasce do custo do EXERCÍCIO, porque foi disso que o manual fez
    regra — e porque encurtar descanso por causa da meta é exatamente o que ele
    proíbe: "nunca reduza o descanso apenas para aumentar desconforto,
    congestão, dificuldade respiratória ou sensação de intensidade".

    Quem quer perder gordura precisa preservar o estímulo de força; quem encurta
    o intervalo troca carga por ofego, e perde músculo justamente na fase em que
    ele é mais difícil de manter. O objetivo ainda influencia — performance pede
    mais recuperação —, só não encurta mais.
    """
    from app.ai.exercise_taxonomy import ORDER_MINOR, order_class_for_pattern

    if taxon.is_compound:
        base = _REST_COMPOUND_BY_SYSTEMIC[taxon.systemic]
    elif order_class_for_pattern(taxon.pattern) == ORDER_MINOR:
        base = _REST_MINOR
    else:
        base = _REST_ISOLATION

    # Série que acaba por falta de ar precisa do fôlego de volta, não só do
    # músculo — e o mesmo vale pra quem declarou condicionamento baixo.
    if taxon.limiter is Limiter.CARDIO:
        base += 30
    if "condicionamento" in (limitations or []):
        base += 30
    if goal == "performance":
        base += 30

    return max(REST_MIN, min(REST_MAX, base))


# --- Quanto tempo a sessão leva (Cap. XVIII Parte J) ------------------------
# "Analise a duração provável da sessão conforme número de séries, aquecimentos,
# descansos, transições." Virou conta porque virou possível: com o descanso saindo
# do exercício, a duração deixa de ser um chute.
#
# As premissas estão todas aqui, à vista, porque a estimativa vale o que elas
# valem:
SEGUNDOS_POR_REP = 3          # mesma constante do training_brain
TRANSICAO_ENTRE_EXERCICIOS_S = 60   # trocar de aparelho, ajustar, achar a carga
PREP_REPS = 10                # aquecimento e feeder são séries curtas
PREP_DESCANSO_S = 45


def exercise_seconds(
    *, sets: int, reps_min: int, reps_max: int, rest_seconds: int, com_aquecimento: bool
) -> int:
    """Segundos de UM exercício: séries de trabalho + descansos + preparação.

    A última série não tem descanso depois dela — quem paga esse tempo é a
    transição pro exercício seguinte, contada separadamente.

    `com_aquecimento` é falso pro exercício que pega um músculo já preparado
    nesta sessão (tríceps depois do supino não reaquece — ver
    `training_brain.needs_warmup`). Sem isso a conta inflaria a sessão inteira.
    """
    reps_medias = (reps_min + reps_max) / 2
    trabalho = sets * reps_medias * SEGUNDOS_POR_REP
    descanso = max(0, sets - 1) * rest_seconds
    preparo = (2 if com_aquecimento else 1) * (PREP_REPS * SEGUNDOS_POR_REP + PREP_DESCANSO_S)
    return int(trabalho + descanso + preparo + TRANSICAO_ENTRE_EXERCICIOS_S)


def session_minutes(exercicios: list[dict], seg_por_serie_medido: float | None = None) -> int:
    """Duração estimada da sessão, em minutos.

    Cada item: {sets, reps_min, reps_max, rest_seconds, com_aquecimento}.

    `seg_por_serie_medido` é o ritmo REAL desta pessoa, cronometrado do início ao
    fim das sessões que ela concluiu (coaching/adaptive.ritmo_da_sessao). As
    constantes acima descrevem uma pessoa genérica que descansa o prescrito e não
    conversa entre séries; quem existe de verdade varia muito em torno disso — e
    o app já mede os dois extremos de cada sessão. Sem histórico, a estimativa é
    a de sempre.

    A mistura é 50/50 de propósito: o medido inclui a vida real (a fila do
    aparelho, a mensagem respondida) e sozinho superestimaria um dia corrido; a
    conta teórica sozinha subestima quem treina sem pressa.
    """
    teorico = sum(exercise_seconds(**e) for e in exercicios)
    if not seg_por_serie_medido or seg_por_serie_medido <= 0:
        return round(teorico / 60)
    series = sum(int(e.get("sets") or 0) for e in exercicios)
    if series <= 0:
        return round(teorico / 60)
    medido = series * seg_por_serie_medido
    return round((teorico * 0.5 + medido * 0.5) / 60)
