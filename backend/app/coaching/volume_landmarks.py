"""Volume semanal de séries de TRABALHO EFETIVAS por grupo muscular.

A régua operacional do produto é uma **faixa-base de 5 a 12 séries semanais por
músculo** (spec §6.1). Ela existe pra matar o vício de "3 séries pra tudo": o
mesmo volume distribuído igual pro corpo inteiro ignora que a pessoa tem
prioridades, que alguns músculos já estão desenvolvidos, e que a capacidade de
recuperação é finita.

As regras, na ordem em que mandam:

1. **Faixa-base 5–12.** É o padrão de quem não tem prioridade nenhuma naquele
   músculo. Nunca é o mesmo número pro corpo inteiro por default.
2. **Ponto forte / já desenvolvido / sem prioridade pode ficar perto de 5.**
   Manter não custa o mesmo que crescer.
3. **Ponto fraco recebe mais: 8 a 16**, conforme prioridade, experiência,
   recuperação e frequência.
4. **20 a 22 séries é EXCEPCIONAL** — no máximo um ou dois músculos por vez, e
   só reduzindo o resto.
5. **Equalização obrigatória.** Quando o volume sobe muito numa prioridade, o
   coach reduz os outros grupos. Recuperação é sistêmica, não por músculo: sem
   isso a pessoa só acumula fadiga e para de progredir em tudo ao mesmo tempo.

Os landmarks MEV/MRV continuam existindo como TETO por músculo — glúteo e
posterior não recuperam o mesmo que costas, e a faixa-base não pode passar por
cima disso.
"""

from __future__ import annotations

from app.coaching import training_brain
from app.models.exercise import MuscleGroup

# (MEV, MRV) semanais por grupo muscular — o teto de recuperação de cada um.
_LANDMARKS: dict[MuscleGroup, tuple[int, int]] = {
    MuscleGroup.CHEST: (8, 20),
    MuscleGroup.BACK: (10, 22),
    MuscleGroup.SHOULDERS: (8, 22),
    MuscleGroup.BICEPS: (8, 20),
    MuscleGroup.TRICEPS: (6, 18),
    MuscleGroup.QUADS: (8, 18),
    MuscleGroup.HAMSTRINGS: (6, 16),
    MuscleGroup.GLUTES: (4, 16),
    MuscleGroup.CALVES: (8, 18),
    MuscleGroup.ABS: (4, 20),
    MuscleGroup.FOREARMS: (4, 16),
    MuscleGroup.TRAPS: (4, 16),
    MuscleGroup.FULL_BODY: (8, 18),
    MuscleGroup.CARDIO: (0, 0),
}

# Faixa-base operacional (spec §6.1). NÃO é garantia universal: é o ponto de
# partida do sistema, individualizado pelas regras abaixo.
BASE_MIN = 5
BASE_MAX = 12

# Ponto fraco: recebe mais volume, dentro do que ainda dá pra recuperar.
WEAK_MIN = 8
WEAK_MAX = 16

# ...e o topo da faixa depende da POSIÇÃO na fila de prioridade.
#
# Os pontos fracos passaram a ser 3 e ORDENADOS (training_brain.WEAK_POINTS_MAX).
# Se os três recebessem o mesmo topo, a ordem seria decorativa: marcar peito,
# costas e bíceps nessa ordem daria exatamente o mesmo plano que marcar bíceps,
# costas e peito. A "Compensação de Volume" do manual só existe porque o
# orçamento de recuperação é finito — alguém tem que receber mais que os outros.
#
# O piso continua sendo WEAK_MIN pros três: mesmo a terceira prioridade nunca
# recebe menos que um ponto fraco recebia antes. O que decai é o TETO.
_WEAK_TOP_BY_RANK: dict[int, int] = {1: WEAK_MAX, 2: 14, 3: 12}

# Onde a faixa COMEÇA na semana 1 do mesociclo, em fração da própria faixa.
#
# Existia um bug silencioso aqui: as duas faixas partiam do piso (0.0), então na
# semana 1 TODO músculo tinha alvo 5 e o ponto fraco tinha 8. Como o blueprint
# entrega naturalmente 4 a 5 vagas por músculo grande, e vaga nenhuma vai abaixo
# de PER_EXERCISE_MIN séries, o alvo de 5 virava 10 séries entregues — e o ponto
# fraco, com alvo 8 e 3 vagas, saía com MENOS volume que costas e ombro. A
# priorização existia no papel e não chegava no treino.
#
# Partindo do meio da faixa, o alvo passa a bater com o que a estrutura da semana
# realmente entrega, e a diferença entre "faixa-base" e "ponto fraco" aparece já
# na primeira semana, não só no fim do ciclo.
BAND_START = 0.5

# ...e ONDE a faixa começa depende do TEMPO POR SESSÃO.
#
# "Tempo por sessão" mandava só no número de EXERCÍCIOS (5/6/8) e não encostava
# no número de séries. Na prática, quem escolhia Curto e quem escolhia Longo
# pedia a mesma quantidade de séries por músculo — o Curto só espremia o mesmo
# volume em menos exercícios, o que é a receita de um treino apertado e de
# músculo ficando sem vaga.
#
# Agora o tempo escolhido é o que define a MARGEM de trabalho:
#   curto -> o piso da faixa. Menos séries, o treino mais rápido possível.
#   médio -> o meio (o comportamento de antes).
#   longo -> mais alto: quem tem tempo aguenta e merece mais volume.
#
# Em todos, o alvo continua subindo ao longo do mesociclo (é a fase de
# acumulação); o que muda é de onde ele parte.
_BAND_START_BY_SESSION = {"curto": 0.0, "medio": 0.5, "longo": 0.75}


def band_start(session_length: str | None) -> float:
    """Onde a faixa começa pro tempo de sessão escolhido. Sem escolha, o meio."""
    return _BAND_START_BY_SESSION.get(session_length or "", BAND_START)

# Excepcional — só com prioridade máxima, em 1 ou 2 músculos, cortando o resto.
EXCEPTIONAL_MIN = 20
EXCEPTIONAL_MAX = 22
MAX_EXCEPTIONAL_MUSCLES = 2

# Iniciante recupera menos volume (fica perto do piso); avançado tolera e
# precisa de mais pra progredir.
_LEVEL_FACTOR = {"iniciante": 0.75, "intermediario": 1.0, "avancado": 1.15}

# Faixa segura de séries por EXERCÍCIO (depois de distribuir o volume do
# músculo entre as vagas que o treinam) — nunca deixa 1 exercício isolado
# carregar todo o volume do músculo nem virar quantidade irrisória.
PER_EXERCISE_MIN = 2
PER_EXERCISE_MAX = 3


def per_exercise_max_with_technique(technique_key: str | None) -> int:
    """PER_EXERCISE_MAX já descontando o peso REAL da técnica prescrita nesse
    exercício — o teto de séries de trabalho EFETIVAS de um exercício é sempre
    3, mesmo quando uma das séries já vale mais de uma sozinha (ex.: muscle
    round e myo-reps contam como 2; uma técnica que vale 2 só deixa espaço pra
    1 série reta a mais, não pras 3 normais de sempre).

    Duas famílias de técnica pesam diferente (training_brain.TECHNIQUE_STRUCTURES):
    - "activation_blocks"/"cluster" TROCAM a última série reta por uma estrutura
      que já vale `weight` séries — sobra só `PER_EXERCISE_MAX - weight + 1`.
    - "drop" ACRESCENTA `weight` séries em cima das que já existiam (não troca
      slot nenhum) — sobra `PER_EXERCISE_MAX - weight`.
    - "cue_only" (superset) não muda a série deste exercício — teto normal.
    """
    if not technique_key:
        return PER_EXERCISE_MAX
    structure = training_brain.technique_structure(technique_key)
    weight = training_brain.TECHNIQUE_SET_WEIGHT.get(technique_key, 1)
    form = structure.get("form")
    if form == "cue_only":
        return PER_EXERCISE_MAX
    if form == "drop":
        return max(1, int(PER_EXERCISE_MAX - weight))
    return max(1, int(PER_EXERCISE_MAX - weight + 1))


def weekly_set_range(muscle: MuscleGroup, level: str | None) -> tuple[int, int]:
    """(MEV, MRV) semanal já ajustado pro nível da pessoa. É o TETO de
    recuperação do músculo — a faixa-base opera por dentro dele."""
    mev, mrv = _LANDMARKS.get(muscle, (8, 18))
    factor = _LEVEL_FACTOR.get(level or "intermediario", 1.0)
    return max(1, round(mev * factor)), max(mev + 2, round(mrv * factor))


# --- COMO A PERIODIZAÇÃO MEXE NO VOLUME (Cap. III, Partes C e D) ------------
# A periodização era a resposta mais ignorada do questionário: ela decidia
# QUANDO o coach oferece deload (`training_brain.offer_deload`) e nada mais. O
# volume subia ao longo do mesociclo para todo mundo, inclusive pra quem tinha
# escolhido LINEAR — que é justamente a estratégia definida pelo volume que NÃO
# sobe. Duas partes do mesmo motor discordando: `offer_deload` já dizia "linear
# nunca desloada" enquanto o volume acumulava como se fosse deslodar.
#
# O manual separa as três com clareza:
#
#   LINEAR       — Volume FIXO. "Após definido, permanece constante durante todo
#                  o ciclo, sofrendo apenas progressões por carga, repetições ou
#                  desempenho, sem alterações planejadas no número de séries."
#                  Faixa própria, 6 a 16.
#   ONDULATÓRIA  — CAMADAS discretas: C1 é o Volume Base, C2 é +20~25% sobre C1,
#                  C3 é +30~40% sobre C2. Degraus, não rampa contínua.
#   AUTOMATIZADA — Volume Base como referência, com ajuste flexível. É a rampa
#                  contínua que o motor já fazia.
VOLUME_FIXO_MIN = 6
VOLUME_FIXO_MAX = 16

# Os saltos das camadas da ondulatória. Meio de cada faixa do manual (20–25% e
# 30–40%), porque o manual dá faixa e o motor precisa de número — e o meio é a
# escolha que não puxa nem pro conservador nem pro agressivo sem motivo.
CAMADA_2_GANHO = 0.225
CAMADA_3_GANHO = 0.35


def camada_do_ciclo(weeks_accumulating: float | None) -> int:
    """Em qual camada da ondulatória a pessoa está (1, 2 ou 3).

    O mesociclo tem MESOCYCLE_WEEKS semanas e três camadas, então cada camada
    dura pouco mais de uma semana. A última semana antes do deload é a camada 3 —
    o topo do acúmulo, que é exatamente o que o deload planejado vem aliviar.
    """
    semanas = max(0.0, weeks_accumulating or 0.0)
    if semanas >= training_brain.MESOCYCLE_WEEKS - 1:
        return 3
    if semanas >= (training_brain.MESOCYCLE_WEEKS - 1) / 2:
        return 2
    return 1


def _multiplicador_da_camada(camada: int) -> float:
    """Quanto a camada multiplica o Volume Base. C1 = 1.0 (é o próprio base)."""
    if camada >= 3:
        return (1 + CAMADA_2_GANHO) * (1 + CAMADA_3_GANHO)
    if camada == 2:
        return 1 + CAMADA_2_GANHO
    return 1.0


def _progress(weeks_accumulating: float | None) -> float:
    """0 a 1 ao longo do mesociclo — o volume sobe do piso da faixa até o topo
    conforme a pessoa acumula semanas sem deload."""
    return min(1.0, max(0.0, (weeks_accumulating or 0.0) / training_brain.MESOCYCLE_WEEKS))


def _dentro_da_faixa(piso: float, topo: float, p: float, inicio: float = BAND_START) -> float:
    """Posição dentro de uma faixa na semana `p` do mesociclo — começando em
    `inicio` da faixa (não no piso) e chegando ao topo no fim do ciclo."""
    return piso + (topo - piso) * (inicio + (1.0 - inicio) * p)


# Extremos de MRV entre todos os músculos — usados pra posicionar cada um
# DENTRO da faixa-base em vez de dar o mesmo número pra todo mundo.
_MRV_MIN = min(mrv for _, mrv in _LANDMARKS.values() if mrv > 0)
_MRV_MAX = max(mrv for _, mrv in _LANDMARKS.values())


def _band_top(muscle: MuscleGroup) -> float:
    """Topo da faixa-base PARA ESTE MÚSCULO.

    A spec é explícita: "não distribuir o mesmo volume para o corpo inteiro por
    padrão". Costas (MRV 22) e glúteo (MRV 16) não recuperam igual, então o
    topo da faixa de cada um é diferente — costas chega nas 12, glúteo para
    antes. A faixa continua sendo 5–12: o que muda é até onde cada músculo vai
    dentro dela.
    """
    _, mrv = _LANDMARKS.get(muscle, (8, 18))
    if _MRV_MAX == _MRV_MIN:
        return BASE_MAX
    posicao = (mrv - _MRV_MIN) / (_MRV_MAX - _MRV_MIN)  # 0..1
    # Mesmo o músculo de menor recuperação chega a ~60% da faixa — o piso da
    # faixa-base continua sendo 5 pra todos.
    return BASE_MIN + (BASE_MAX - BASE_MIN) * (0.6 + 0.4 * posicao)


def weekly_target_sets(
    muscle: MuscleGroup,
    level: str | None,
    weeks_accumulating: float | None,
    *,
    priority: str = "normal",
    session_length: str | None = None,
    recovery: float = 1.0,
    tolerance: float = 1.0,
    periodization: str | None = None,
) -> int:
    """Séries semanais efetivas pro músculo. `priority`:

    - "baixa"       -> ponto forte / já desenvolvido / sem prioridade: perto de 5
    - "normal"      -> faixa-base 5–12, subindo ao longo do mesociclo
    - "alta"        -> ponto fraco 1º da fila: 8–16
    - "alta_2"      -> ponto fraco 2º da fila: 8–14
    - "alta_3"      -> ponto fraco 3º da fila: 8–12
    - "excepcional" -> 20–22 (só 1–2 músculos, e com o resto reduzido)

    `recovery` é o fator de training_brain.recovery_factor (sono, estresse, dor
    entre sessões, outro esporte). Ele multiplica o alvo DEPOIS da faixa e ANTES
    do teto — quem dorme mal treina o mesmo desenho de treino com menos série,
    não um treino diferente.

    `session_length` decide de ONDE a faixa parte (ver `band_start`): quem pediu
    um treino curto trabalha na margem baixa, quem tem tempo trabalha na alta.

    O PONTO FRACO é a exceção deliberada: ele mantém a faixa alta em qualquer
    tempo de sessão. Num treino curto o que se espreme é o que NÃO é prioridade —
    espremer os dois lados igualmente devolveria o problema original (marcar um
    ponto fraco e não ver diferença), só que por outro caminho.

    `tolerance` é o que o coach APRENDEU vendo a pessoa treinar
    (coaching/adaptive.tolerancia_a_volume): quanto do prescrito ela de fato
    executa e quantas sessões termina. Enquanto `recovery` vem do que ela DISSE
    no questionário, este vem do que ela FEZ — e por isso pesa depois dele.
    Prescrever 16 séries para quem registra 9 não é ambição, é ignorar o
    histórico e transformar o plano em ficção.

    `periodization` decide COMO o alvo evolui dentro do mesociclo (Cap. III
    Partes C e D) — ver o bloco de constantes acima. Sem ela, "auto".

    O teto de recuperação do músculo (MRV ajustado pelo nível) vence sempre:
    prescrever 16 séries de posterior porque virou prioridade não faz o
    posterior recuperar 16.
    """
    _, mrv = weekly_set_range(muscle, level)
    modo = training_brain.valid_periodization(periodization)
    # LINEAR trabalha com Volume Fixo: o alvo não anda com as semanas. Zerar o
    # progresso é o que torna isso verdade em todos os ramos abaixo de uma vez —
    # o volume passa a ser função só do músculo, do nível e da prioridade, que é
    # a definição de "fixo" do manual. A progressão dela vem por carga e
    # repetições, no motor de progressão.
    p = 0.0 if modo == "linear" else _progress(weeks_accumulating)
    fator = _LEVEL_FACTOR.get(level or "intermediario", 1.0)
    inicio = band_start(session_length)

    if priority == "baixa":
        # Ponto forte / já desenvolvido / FINANCIADOR de um ponto fraco: manter
        # custa pouco — fica no piso da faixa.
        alvo = BASE_MIN
    elif priority.startswith("alta"):
        # Prioridade não encolhe com o relógio — ver o docstring. O topo é o da
        # POSIÇÃO na fila: 1º 16, 2º 14, 3º 12 (ver _WEAK_TOP_BY_RANK).
        rank = 1 if priority == "alta" else int(priority.rsplit("_", 1)[-1])
        alvo = _dentro_da_faixa(WEAK_MIN, _WEAK_TOP_BY_RANK.get(rank, WEAK_MAX), p)
    elif priority == "excepcional":
        alvo = _dentro_da_faixa(EXCEPTIONAL_MIN, EXCEPTIONAL_MAX, p)
    else:
        # Faixa-base, com o TOPO próprio de cada músculo (§6.1: nada de mesmo
        # volume pro corpo inteiro) e o INÍCIO dado pelo tempo de sessão.
        alvo = _dentro_da_faixa(BASE_MIN, _band_top(muscle), p, inicio)

    # ONDULATÓRIA: as camadas multiplicam o Volume Base em degraus (Cap. III
    # Parte D). "As prioridades musculares devem permanecer exatamente as
    # mesmas" — por isso a camada entra DEPOIS de a prioridade já ter escolhido
    # a faixa, multiplicando o que saiu dela, em vez de mexer na faixa.
    if modo == "ondulatoria":
        alvo *= _multiplicador_da_camada(camada_do_ciclo(weeks_accumulating))

    alvo = round(alvo * fator * recovery * tolerance)

    # LINEAR tem faixa própria (6–16), e ela é um teto/piso do resultado, não uma
    # faixa de partida: o manual descreve o Volume Fixo como um número escolhido
    # dentro de 6–16 e mantido. Quem financia um ponto fraco pode ficar abaixo de
    # 6? Não — na linear não existe camada pra compensar depois, então o piso
    # protege o financiador de passar o ciclo inteiro em volume de manutenção.
    if modo == "linear":
        alvo = max(VOLUME_FIXO_MIN, min(alvo, VOLUME_FIXO_MAX))

    # --- VOLUME MÁXIMO PERMITIDO (Cap. III, Parte E) ------------------------
    # "Músculos prioritários podem atingir até 22 séries efetivas semanais [...]
    # músculos SEM prioridade normalmente devem permanecer dentro da faixa
    # correspondente ao Volume Base."
    #
    # Sem este teto as camadas da ondulatória levavam peito não-prioritário a 18
    # séries na camada 3 — mais que o topo da faixa de um PONTO FRACO de segunda
    # posição. Isso inverte a Compensação de Volume: a camada é justamente onde o
    # manual manda o aumento "continuar priorizando exclusivamente os músculos
    # definidos como prioridade". Quem não é prioridade para no topo da
    # faixa-base; a camada existe pros que são.
    if priority == "excepcional":
        teto = mrv
    elif priority.startswith("alta"):
        teto = min(mrv, EXCEPTIONAL_MAX)
    else:
        teto = min(mrv, BASE_MAX)
    return max(1, min(alvo, teto))


def weekly_plan(
    muscles: list[MuscleGroup],
    level: str | None,
    weeks_accumulating: float | None,
    *,
    weak_points: list[MuscleGroup] | None = None,
    exceptional: list[MuscleGroup] | None = None,
    session_length: str | None = None,
    recovery: float = 1.0,
    tolerance: float = 1.0,
    periodization: str | None = None,
) -> dict[MuscleGroup, int]:
    """O volume semanal de TODOS os músculos da semana, de uma vez.

    Precisa ser calculado junto (e não músculo a músculo) por causa da
    **equalização obrigatória** (§6.1): a capacidade de recuperação é sistêmica,
    então o que sobe num ponto fraco tem que descer em outro lugar. Calcular
    isolado é como cada área da empresa pedir orçamento sem olhar o caixa.

    `weak_points` vem ORDENADO — a posição na lista é a prioridade declarada no
    questionário, e é ela que define o topo da faixa de cada um.
    """
    ordem = list(dict.fromkeys(weak_points or []))  # sem repetição, ordem mantida
    weak = set(ordem)
    rank = {m: i + 1 for i, m in enumerate(ordem)}
    # Excepcional é raro por definição: no máximo 2 músculos, e só entre os que
    # já são ponto fraco (ninguém leva um músculo sem prioridade a 22 séries).
    exc = [m for m in (exceptional or []) if m in weak][:MAX_EXCEPTIONAL_MUSCLES]

    def prioridade(m: MuscleGroup) -> str:
        if m in exc:
            return "excepcional"
        if m in weak:
            pos = rank[m]
            return "alta" if pos == 1 else f"alta_{pos}"
        # --- EQUALIZAÇÃO ----------------------------------------------------
        # Havendo ponto fraco, quem NÃO é prioridade vira financiador e desce pro
        # piso da faixa (§6.1: "o coach reduz os outros grupos"). Não é
        # penalidade: manter um músculo custa muito menos que fazer ele crescer,
        # e a recuperação é sistêmica — sem essa troca a pessoa só acumula fadiga
        # e para de progredir em tudo ao mesmo tempo.
        #
        # A versão anterior fazia isso como um rodízio que cedia séries só até
        # cobrir o EXCESSO do ponto fraco. Como os dois lados partiam do piso da
        # faixa, não havia excesso nenhum pra cobrir: o rodízio rodava zero vezes
        # e trocar o ponto fraco não mudava volume nenhum. Agora a redução é o
        # próprio alvo de quem não é prioridade.
        return "baixa" if weak else "normal"

    return {
        m: weekly_target_sets(
            m, level, weeks_accumulating,
            priority=prioridade(m), session_length=session_length,
            recovery=recovery, tolerance=tolerance, periodization=periodization,
        )
        for m in muscles
    }


def slot_range(target_sets: int) -> tuple[int, int]:
    """(mínimo, máximo) de EXERCÍCIOS que entregam `target_sets` séries semanais.

    Uma vaga entrega de PER_EXERCISE_MIN a PER_EXERCISE_MAX séries de trabalho
    efetivas, então o alvo semanal define uma faixa de quantos exercícios daquele
    músculo a semana comporta. Vagas a mais que o máximo NÃO conseguem entregar o
    alvo: elas empurram o volume pra cima (nenhuma vaga vai abaixo do mínimo), que
    era exatamente como a redução dos financiadores era desfeita — costas com
    alvo 5 e 5 vagas saía com 10 séries.

    O mínimo de 2 vagas nunca é violado por quem chama isto: frequência de 2×/
    semana por grupo muscular é regra do produto, não consequência de volume.
    """
    minimo = max(1, -(-target_sets // PER_EXERCISE_MAX))  # ceil
    maximo = max(minimo, target_sets // PER_EXERCISE_MIN)
    return minimo, maximo
