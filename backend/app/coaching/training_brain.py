"""O 'cérebro de treino' do Coaching.

Centraliza, num lugar só e SEM IA, as preferências de treino da pessoa (ponto
fraco, tempo por sessão, cardio, periodização) e as REGRAS que elas disparam:
qual técnica avançada usar em cada período, e quando o coach oferece deload
conforme a periodização escolhida.

Tudo determinístico e à vista, como o resto do coach — o mesmo input sempre gera
o mesmo output. A camada de conversa (IA Pro) só traduz isto; não muda a decisão.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone

from app.models.exercise import MuscleGroup

# ---------------------------------------------------------------------------
# PONTO FRACO — grupos que fazem sentido priorizar nos acessórios. (Valores
# batem com o enum MuscleGroup; o motor de treino já sabe priorizar.)
# ---------------------------------------------------------------------------
WEAK_POINTS: list[tuple[str, str]] = [
    ("chest", "Peito"),
    ("back", "Costas"),
    ("shoulders", "Ombros"),
    ("biceps", "Bíceps"),
    ("triceps", "Tríceps"),
    ("quads", "Quadríceps"),
    ("hamstrings", "Posterior de coxa"),
    ("glutes", "Glúteos"),
    ("calves", "Panturrilha"),
]
WEAK_POINT_LABEL: dict[str, str] = dict(WEAK_POINTS)


def valid_weak_point(value: str | None) -> str | None:
    """None (nenhum) ou um grupo válido; qualquer outra coisa vira None."""
    return value if value in WEAK_POINT_LABEL else None


# Quantos pontos fracos a pessoa pode priorizar de uma vez, EM ORDEM.
#
# Eram 2 sem ordem. Viraram 3 ORDENADOS porque a ordem muda o cálculo: o manual
# de regras trata prioridade como uma fila que consome um orçamento finito de
# recuperação (a "Compensação de Volume"), não como um conjunto onde todo mundo
# recebe igual. Priorizar peito, costas e braço "empatados" é o mesmo que não
# priorizar nada — alguém tem que ser o primeiro a receber o volume que sobra.
#
# Três continua sendo teto: acima disso não sobra financiador. Com 3 prioridades
# já são 6 músculos no piso da faixa bancando a conta (ver volume_landmarks).
WEAK_POINTS_MAX = 3

# ---------------------------------------------------------------------------
# PREFERÊNCIAS DE EXERCÍCIO — o que a pessoa quer (ou não quer) no treino.
# ---------------------------------------------------------------------------
# Eram um campo de texto livre ("Exercícios que você gosta ou não quer"). O
# texto era guardado e NUNCA lido por nada: quem escrevia "prefiro máquinas e
# exercícios estáveis" via o coach montar agachamento livre do mesmo jeito.
# Viraram opções porque opção o motor CONSEGUE obedecer — cada uma abaixo tem
# um efeito determinístico na escolha dos exercícios (ver
# workout_builder.filtrar_por_preferencia). O campo de texto continua existindo
# ao lado, pro que não couber aqui, e vai pro contexto do coach de IA.
EXERCISE_PREFS: list[tuple[str, str, str]] = [
    ("maquinas", "Prefiro máquinas e exercícios estáveis",
     "Máquinas e cabos na frente. Bom pra quem treina sozinho ou quer menos exigência de equilíbrio."),
    ("peso_livre", "Prefiro peso livre (barra e halteres)",
     "Barra e halteres na frente das máquinas."),
    ("sem_agachamento_livre", "Evitar agachamento com barra nas costas",
     "Troca por leg press, hack, agachamento em máquina e afins."),
    ("sem_acima_da_cabeca", "Evitar exercícios acima da cabeça",
     "Sem desenvolvimento militar e variações — comum com ombro sensível."),
    ("sem_impacto", "Evitar impacto e salto",
     "Sem pliometria, corrida e pulo — comum com joelho ou lombar sensíveis."),
    ("unilateral", "Gosto de exercícios unilaterais",
     "Um lado por vez (afundo, remada serrote, leg press unilateral) ganham prioridade."),
]
EXERCISE_PREFS_VALUES = {v for v, _, _ in EXERCISE_PREFS}

# Preferências que se contradizem: marcar as duas não faz sentido, e a segunda
# escolhida ganha (o app já impede, isto é a rede de segurança do servidor).
_PREFS_OPOSTAS = {("maquinas", "peso_livre"), ("peso_livre", "maquinas")}


def valid_exercise_prefs(valores) -> list[str]:
    """Sanitiza a lista vinda do app: só valores conhecidos, sem repetição e
    sem par contraditório (máquinas × peso livre)."""
    if not valores:
        return []
    out: list[str] = []
    for v in valores:
        v = str(v).strip()
        if v not in EXERCISE_PREFS_VALUES or v in out:
            continue
        if any((v, j) in _PREFS_OPOSTAS for j in out):
            continue
        out.append(v)
    return out


# ---------------------------------------------------------------------------
# AS RESPOSTAS ESTRUTURADAS DO QUESTIONÁRIO NOVO
# ---------------------------------------------------------------------------
# Regra de ouro deste bloco: **toda opção aqui precisa ter efeito determinístico
# no motor**. O questionário antigo tinha 6 campos de texto livre (histórico,
# lesões, preferências, alimentos, medicamentos, observações) que eram gravados
# e nunca lidos por regra nenhuma — quem escrevia "dor no ombro em supino" via o
# coach montar supino do mesmo jeito. Texto livre o motor não consegue obedecer;
# opção ele consegue.
#
# Por isso cada lista abaixo nasce junto com o lugar que a consome. Se uma
# resposta não muda nenhum número do plano, ela não deveria estar sendo
# perguntada.

# --- Tempo de treino consistente -> nível de experiência --------------------
# Substitui a auto-avaliação ("você é iniciante, intermediário ou avançado?").
# Tempo é verificável; auto-avaliação é sistematicamente inflada, e o nível
# alimenta o fator de volume (_LEVEL_FACTOR) e a régua de RIR. Quando alguém se
# promove a avançado sozinho, ganha 15% mais volume sem ter a recuperação pra
# bancar. "de forma consistente" está no enunciado de propósito: resolve o caso
# de quem treinou 6 anos e parou 3.
TRAINING_TIME: list[tuple[str, str, str]] = [
    ("menos_6m", "Menos de 6 meses", "iniciante"),
    ("6m_1a", "De 6 meses a 1 ano", "iniciante"),
    ("1_3a", "De 1 a 3 anos", "intermediario"),
    ("3_5a", "De 3 a 5 anos", "intermediario"),
    ("mais_5a", "Mais de 5 anos", "avancado"),
]
TRAINING_TIME_VALUES = {v for v, _, _ in TRAINING_TIME}
_TRAINING_TIME_LEVEL = {v: nivel for v, _, nivel in TRAINING_TIME}


def experience_from_training_time(value: str | None) -> str | None:
    """Nível de experiência derivado do tempo de treino. None quando a pessoa
    ainda não respondeu — aí quem chama mantém o nível que já estava no perfil.

    O mapa é deliberadamente CONSERVADOR (3–5 anos ainda é intermediário): errar
    pra baixo custa um pouco de volume, errar pra cima custa recuperação que a
    pessoa não tem.
    """
    return _TRAINING_TIME_LEVEL.get(str(value or ""))


# O caminho inverso, só pra MIGRAÇÃO: quem já usava o app respondeu o nível na
# auto-avaliação antiga e não tem `training_time` gravado. Sem isto o campo (que
# é obrigatório) apareceria em branco e a pessoa ficaria travada fora do próprio
# plano até responder de novo. Escolhe a faixa MAIS BAIXA de cada nível — a
# pessoa confirma ou corrige na tela, e enquanto não corrigir o nível dela
# continua exatamente o que era.
_LEVEL_TRAINING_TIME = {"iniciante": "6m_1a", "intermediario": "1_3a", "avancado": "mais_5a"}


def training_time_from_experience(level: str | None) -> str | None:
    return _LEVEL_TRAINING_TIME.get(str(level or ""))


# --- Capacidade de estimar RIR ---------------------------------------------
# Cap. XII do manual: "a precisão do RIR deve ser construída e validada, não
# presumida". Quem não sabe estimar recebe RIR-alvo mais conservador e não
# recebe técnica que depende de chegar perto da falha com precisão.
RIR_ACCURACY: list[tuple[str, str, str]] = [
    ("sim", "Sim, consigo estimar bem",
     "Você sabe dizer quantas repetições ainda restavam ao terminar a série."),
    ("mais_ou_menos", "Mais ou menos",
     "Tem uma noção, mas erra às vezes."),
    ("nao", "Não sei estimar",
     "Sem problema — eu deixo uma margem maior de segurança até você pegar o jeito."),
]
RIR_ACCURACY_VALUES = {v for v, _, _ in RIR_ACCURACY}

# --- Regiões de lesão / dor -------------------------------------------------
# Uma região marcada aqui filtra exercícios de verdade (é o que o texto livre
# nunca conseguiu fazer). Os valores batem com os padrões de movimento que o
# montador já conhece.
BODY_REGIONS: list[tuple[str, str]] = [
    ("ombro", "Ombro"),
    ("cotovelo", "Cotovelo"),
    ("punho", "Punho ou mão"),
    ("cervical", "Pescoço"),
    ("lombar", "Lombar (parte baixa das costas)"),
    ("quadril", "Quadril"),
    ("joelho", "Joelho"),
    ("tornozelo", "Tornozelo ou pé"),
]
BODY_REGION_VALUES = {v for v, _ in BODY_REGIONS}

# Intensidade da dor. 7+ não é ajuste de treino, é encaminhamento: o app não
# diagnostica (regra 8 do produto) e não tenta "trabalhar em volta" de dor forte.
PAIN_INTENSITY: list[tuple[str, str, str]] = [
    ("leve", "Leve (1 a 3)", "Incomoda, mas dá pra treinar normalmente."),
    ("moderada", "Moderada (4 a 6)", "Atrapalha o movimento e piora durante a série."),
    ("forte", "Forte (7 a 10)", "Dói bastante ou impede o movimento."),
]
PAIN_INTENSITY_VALUES = {v for v, _, _ in PAIN_INTENSITY}

# --- Limitações funcionais --------------------------------------------------
LIMITATIONS: list[tuple[str, str, str]] = [
    ("mobilidade", "Mobilidade reduzida",
     "Dificuldade de chegar na amplitude completa em alguns movimentos."),
    ("equilibrio", "Equilíbrio",
     "Instabilidade em pé ou em exercícios unilaterais."),
    ("respiracao", "Respiração",
     "Falta de ar com facilidade — asma, rinite ou similar."),
    ("condicionamento", "Condicionamento baixo",
     "Cansa rápido entre as séries."),
]
LIMITATION_VALUES = {v for v, _, _ in LIMITATIONS}

# --- Academia cheia ---------------------------------------------------------
# Cap. XVIII Parte J: uma prescrição que depende de reservar 2 estações numa
# academia lotada não é executável. Marcar "cheia" desliga superset e prioriza
# exercício de equipamento abundante.
GYM_CROWDING: list[tuple[str, str, str]] = [
    ("vazia", "Costuma estar tranquila", "Dá pra usar qualquer aparelho na hora."),
    ("normal", "Movimento normal", "Às vezes espera um pouco."),
    ("cheia", "Costuma estar cheia",
     "Eu evito exercícios que dependem de segurar duas estações ao mesmo tempo."),
]
GYM_CROWDING_VALUES = {v for v, _, _ in GYM_CROWDING}

# --- Equipamento em casa ----------------------------------------------------
HOME_EQUIPMENT: list[tuple[str, str]] = [
    ("halteres", "Halteres"),
    ("barra", "Barra e anilhas"),
    ("banco", "Banco"),
    ("elasticos", "Elásticos ou faixas"),
    ("barra_fixa", "Barra fixa"),
    ("polia", "Polia ou crossover"),
    ("kettlebell", "Kettlebell"),
    ("maquina", "Alguma máquina"),
]
HOME_EQUIPMENT_VALUES = {v for v, _ in HOME_EQUIPMENT}

# --- Divisão semanal preferida ---------------------------------------------
# Bro-split (um músculo por dia) NÃO é oferecido: regra 6 do produto exige
# frequência mínima de 2×/semana por grupo, e o montador tem trava dura pra
# isso. Oferecer uma opção que o motor vai recusar seria mentir na tela.
SPLIT_PREFERENCES: list[tuple[str, str, str]] = [
    ("auto", "Deixa o app escolher",
     "Escolho a melhor divisão pros dias que você tem. É o recomendado."),
    # A faixa de dias de cada uma é acrescentada na tela por
    # `questionnaire._faixa_de_dias`, direto de `methods.SPLIT_DAY_RANGE` —
    # texto e motor não podem discordar sobre o que cabe.
    ("full_body", "Corpo inteiro todo treino",
     "Cada treino passa pelo corpo todo."),
    ("upper_lower", "Superior e inferior",
     "Alterna treino de cima e de baixo."),
    ("push_pull_legs", "Empurrar, puxar e pernas",
     "Peito/ombro/tríceps num dia, costas/bíceps noutro, pernas noutro."),
]
SPLIT_PREFERENCE_VALUES = {v for v, _, _ in SPLIT_PREFERENCES}

# --- Preferência de carga ---------------------------------------------------
# Entrada direta do Cap. XI (faixa de repetições): desloca a faixa dentro do que
# o exercício permite, sem nunca passar de 15 repetições nem descer abaixo do que
# o exercício suporta com segurança.
LOAD_PREFERENCE: list[tuple[str, str, str]] = [
    ("pesado", "Carga alta, menos repetições", "Trabalho mais perto de 5 a 8 repetições."),
    ("moderado", "Carga moderada", "A faixa de 8 a 12, que é o meio do caminho."),
    ("leve", "Carga mais leve, mais repetições",
     "Faixa de 12 a 15. Costuma pegar melhor com articulação sensível."),
    ("indiferente", "Tanto faz, escolha por mim",
     "Eu escolho a faixa por exercício, que é o ideal."),
]
LOAD_PREFERENCE_VALUES = {v for v, _, _ in LOAD_PREFERENCE}

# --- Conforto perto da falha ------------------------------------------------
# Entrada direta do Cap. XII (RIR-alvo).
FAILURE_COMFORT: list[tuple[str, str, str]] = [
    ("evito", "Prefiro parar com folga",
     "Você termina a série sentindo que ainda tinha várias repetições."),
    ("as_vezes", "Às vezes, em alguns exercícios",
     "Aceita chegar perto do limite em máquina, mas não em peso livre."),
    ("sim", "Sim, gosto de treinar perto da falha",
     "Confortável em terminar a série sem sobrar quase nada."),
]
FAILURE_COMFORT_VALUES = {v for v, _, _ in FAILURE_COMFORT}

# --- Recuperação ------------------------------------------------------------
# Estes quatro campos entram JUNTOS num único fator de recuperação, que desloca o
# volume semanal dentro da faixa MEV–MRV. Separados eles não decidiriam nada;
# juntos são a "capacidade de recuperação" que o Cap. III exige antes de fechar
# o volume. Por isso são 4 perguntas curtas e não 7 (o manual pergunta sono,
# qualidade do sono, estresse, trabalho físico, esporte, recuperação e dor
# prolongada — trabalho físico já é o `activity_level`, e "dor prolongada" e
# "chega recuperado" são a mesma pergunta feita duas vezes).
SLEEP_QUALITY: list[tuple[str, str]] = [
    ("boa", "Durmo bem"),
    ("media", "Durmo mais ou menos"),
    ("ruim", "Durmo mal"),
]
STRESS_LEVEL: list[tuple[str, str]] = [
    ("baixo", "Tranquilo na maior parte do tempo"),
    ("medio", "Puxado, mas administrável"),
    ("alto", "Bem estressante"),
]
RECOVERY_BETWEEN: list[tuple[str, str, str]] = [
    ("recuperado", "Chego inteiro no treino seguinte", "Sem dor limitante, rendendo igual."),
    ("as_vezes", "Às vezes chego dolorido", "Acontece, mas não atrapalha muito."),
    ("dolorido", "Quase sempre dolorido ou rendendo menos",
     "Eu reduzo o volume até isso melhorar."),
]
OTHER_SPORT: list[tuple[str, str]] = [
    ("nao", "Não pratico outro esporte"),
    ("leve", "1 a 2 vezes por semana, leve"),
    ("moderado", "3 a 4 vezes por semana"),
    ("intenso", "5 ou mais vezes"),
]
SLEEP_QUALITY_VALUES = {v for v, _ in SLEEP_QUALITY}
STRESS_LEVEL_VALUES = {v for v, _ in STRESS_LEVEL}
RECOVERY_BETWEEN_VALUES = {v for v, _, _ in RECOVERY_BETWEEN}
OTHER_SPORT_VALUES = {v for v, _ in OTHER_SPORT}


def one_of(value, permitidos: set[str]) -> str | None:
    """Uma resposta de escolha única: o valor quando ele é conhecido, None
    quando não é (inclusive quando vem vazio). None sempre significa "não
    respondeu", e quem lê aplica o padrão seguro."""
    v = str(value or "").strip()
    return v if v in permitidos else None


def many_of(valores, permitidos: set[str]) -> list[str]:
    """Uma resposta de múltipla escolha: só valores conhecidos, sem repetição e
    na ordem em que vieram."""
    out: list[str] = []
    for v in valores or []:
        v = str(v).strip()
        if v in permitidos and v not in out:
            out.append(v)
    return out


FOOD_DISLIKES_MAX_ITEMS = 20
FOOD_DISLIKE_MAX_LEN = 40


def parse_food_dislikes(value) -> list[str]:
    """"Alimentos que não come" virou texto livre — aceita tanto a STRING do
    formulário (separada por vírgula) quanto a LISTA que o chat já manda
    (`chat_tools._AJUSTES["alimentos_que_nao_come"]`). Aqui só limpa (sem
    vazio, sem duplicata, com teto de tamanho/quantidade); se o nome digitado
    é um alimento que o motor sabe excluir é decidido depois, na hora de montar
    a dieta, por `app.data.food_roles.normalize_tokens` — que também avisa o
    que não reconheceu (`unsupported`), em vez de fingir que aplicou."""
    brutos = value.split(",") if isinstance(value, str) else list(value or [])
    limpos: list[str] = []
    vistos: set[str] = set()
    for item in brutos:
        texto = str(item).strip()[:FOOD_DISLIKE_MAX_LEN]
        chave = texto.lower()
        if texto and chave not in vistos:
            vistos.add(chave)
            limpos.append(texto)
    return limpos[:FOOD_DISLIKES_MAX_ITEMS]


# Quanto cada resposta de recuperação desloca o volume semanal. Somados a 1.0,
# viram o fator que multiplica o alvo de séries (volume_landmarks).
_RECOVERY_DELTA: dict[str, dict[str, float]] = {
    "sleep_quality":  {"boa": +0.05, "media": 0.0, "ruim": -0.10},
    "stress_level":   {"baixo": +0.05, "medio": 0.0, "alto": -0.05},
    "recovery_between": {"recuperado": +0.05, "as_vezes": 0.0, "dolorido": -0.15},
    "other_sport":    {"nao": 0.0, "leve": -0.03, "moderado": -0.08, "intenso": -0.15},
}
# Piso e teto do fator. O piso existe pra "tudo ruim" reduzir o treino sem
# apagá-lo (um plano de 60% do volume ainda é um plano); o teto, pra dormir bem
# não virar licença pra volume ilimitado — quem manda no topo continua sendo o
# MRV do músculo.
RECOVERY_FACTOR_MIN = 0.70
RECOVERY_FACTOR_MAX = 1.15


def recovery_factor(profile) -> float:
    """O quanto a recuperação da pessoa desloca o volume semanal, de 0.70 a 1.15.

    É AQUI que sono, estresse, dor entre sessões e outro esporte viram número.
    Sozinha, nenhuma dessas respostas decide nada — quatro perguntas curtas que
    produzem um fator só, em vez das sete do manual produzindo texto nenhum.

    Perfil sem resposta nenhuma devolve 1.0 (neutro): o fator só existe pra
    ajustar quem respondeu, nunca pra punir quem pulou.
    """
    fator = 1.0
    for campo, deltas in _RECOVERY_DELTA.items():
        fator += deltas.get(str(getattr(profile, campo, None) or ""), 0.0)
    return max(RECOVERY_FACTOR_MIN, min(RECOVERY_FACTOR_MAX, round(fator, 3)))


def valid_weak_points(values) -> list[str]:
    """Normaliza uma lista de pontos fracos: só grupos válidos, sem repetição e
    no máximo WEAK_POINTS_MAX. Aceita None/valores soltos sem quebrar."""
    out: list[str] = []
    for v in values or []:
        g = valid_weak_point(v)
        if g and g not in out:
            out.append(g)
        if len(out) >= WEAK_POINTS_MAX:
            break
    return out


def resolve_weak_points(profile) -> list[str]:
    """Os pontos fracos efetivos de um perfil: a lista nova (`weak_points`) e, se
    ela estiver vazia, cai no `weak_point` singular legado — assim perfis antigos
    não perdem a escolha ao migrar."""
    lista = valid_weak_points(getattr(profile, "weak_points", None))
    if lista:
        return lista
    legado = valid_weak_point(getattr(profile, "weak_point", None))
    return [legado] if legado else []


# --- BLOCO DE ESPECIALIZAÇÃO -----------------------------------------------
# Priorizar um músculo não é de graça: os outros descem pro piso da faixa e
# passam o bloco em manutenção (volume_landmarks.weekly_plan). É a troca certa —
# e tem prazo de validade. Um bloco de especialização dura 4 a 8 semanas; depois
# disso a pessoa precisa decidir de novo, porque o corpo inteiro parado por tempo
# indeterminado deixa de ser priorização e vira só um treino desequilibrado.
#
# 6 semanas: o meio da faixa consagrada, e tempo suficiente pra o ponto fraco
# atravessar um mesociclo inteiro (MESOCYCLE_WEEKS) com volume alto e ainda
# aparecer no espelho.
SPECIALIZATION_WEEKS = 6


def specialization_weeks(since, now) -> float | None:
    """Há quantas semanas o bloco de especialização está em curso. None quando
    não há bloco (nenhum ponto fraco marcado, ou perfil antigo sem a data)."""
    if since is None:
        return None
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return max(0.0, (now - since).total_seconds() / (7 * 86400))


def specialization_due(since, now) -> bool:
    """O bloco já cumpriu o prazo e o coach precisa cobrar a decisão?"""
    semanas = specialization_weeks(since, now)
    return semanas is not None and semanas >= SPECIALIZATION_WEEKS


def apply_weak_points(profile, valores, now) -> list[str]:
    """Grava os pontos fracos no perfil e mantém o relógio do bloco em dia.

    Existe pra o relógio não depender de quem chama: os pontos fracos são
    escritos em dois lugares (o questionário e as preferências de treino), e uma
    data que só um dos dois carimbasse seria pior que data nenhuma — o coach
    cobraria a revisão de umas pessoas e de outras não.

    A data só é REINICIADA quando a escolha muda de verdade. Reescrever a mesma
    escolha (salvar o questionário de novo sem mexer no ponto fraco) não zera o
    relógio: senão bastaria abrir e salvar as preferências pra a especialização
    nunca vencer, que é justamente o que este mecanismo existe pra impedir.

    A comparação é de LISTA, não de conjunto: a ordem é a prioridade, e trocar
    peito↔costas de posição muda quem recebe o volume de topo. É uma
    especialização nova, e o relógio dela começa agora.
    """
    novos = valid_weak_points(valores)
    atuais = valid_weak_points(getattr(profile, "weak_points", None))
    profile.weak_points = novos
    profile.weak_point = novos[0] if novos else None  # mantém o legado em sincronia
    if not novos:
        profile.weak_points_since = None
    elif novos != atuais or getattr(profile, "weak_points_since", None) is None:
        profile.weak_points_since = now
    return novos


# ---------------------------------------------------------------------------
# DIAS por semana que a pessoa pode treinar (2–6). É o que define quantos
# treinos o coach monta. None = automático (infere dos dias do onboarding).
#
# Por que 2 no piso e 6 no teto (decisão de produto, 2026-07-30):
#   - 2 dias não é o ideal (cada grupo treina 2x/semana só se as duas sessões
#     forem full body), mas é treino de verdade e melhor que não treinar.
#   - 7 dias NÃO EXISTE: sem nenhum dia de folga não há recuperação, e o
#     próprio motor de volume trabalha com a fadiga sendo sistêmica. Quem marca
#     7 dias disponíveis no onboarding é montado com 6 (o clamp abaixo).
# ---------------------------------------------------------------------------
TRAINING_DAYS_MIN = 2
TRAINING_DAYS_MAX = 6
TRAINING_DAYS_OPTIONS: list[int] = list(range(TRAINING_DAYS_MIN, TRAINING_DAYS_MAX + 1))


def valid_training_days(value: int | None) -> int | None:
    """None (automático) ou um inteiro dentro de 2–6; fora disso vira None."""
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if TRAINING_DAYS_MIN <= n <= TRAINING_DAYS_MAX else None


# ---------------------------------------------------------------------------
# TEMPO por sessão -> alvo de exercícios por treino. Curto/Médio/Longo.
# ---------------------------------------------------------------------------
# value, rótulo, tempo aproximado, exercícios-alvo por sessão
#
# Os tempos foram CORRIGIDOS em 2026-07-31, e não por gosto: assim que o descanso
# passou a sair do exercício (`prescription.rest_seconds`), deu pra medir a
# duração real do que o motor monta. Os números antigos — 45–70, 70–100 e
# 100–120 — prometiam quase o dobro do que o treino entrega. Medido nas 15
# combinações de tempo × frequência (2 a 6 dias): Curto sai entre 27 e 42 min,
# Médio entre 27 e 68, Longo entre 31 e 72.
#
# Por que uma média e não uma faixa: a duração cai bastante conforme a FREQUÊNCIA
# sobe, porque o volume semanal se distribui em mais dias. Quem treina Longo em 3
# dias faz ~70 min; em 6 dias, ~40. Uma faixa que cobrisse os dois extremos
# ("31–72 min") não ajudaria ninguém a escolher, e as faixas de Médio e Longo se
# sobreporiam quase inteiras. A estimativa EXATA do plano de cada pessoa é
# calculada na montagem e sai em `duration_note` — este texto aqui é só a
# ordem de grandeza pra escolher na hora de responder.
SESSION_LENGTHS: list[tuple[str, str, str, int]] = [
    ("curto", "Curto", "30–45 min", 5),
    ("medio", "Médio", "45–60 min", 6),
    ("longo", "Longo", "60+ min", 8),
]
_SESSION_ORDER = [v for v, _, _, _ in SESSION_LENGTHS]

# PISO de exercícios por sessão. Abaixo disso não é um treino curto — é um treino
# pela metade: não dá pra cobrir os padrões de movimento do dia, alternar
# estímulos (Princípio 5) nem fechar as regiões da semana (Princípio 6) com 3 ou
# 4 vagas. É o mesmo número do tempo "Curto", que já é o menor treino que o
# produto oferece — ninguém pode receber menos do que quem pediu o mais curto.
#
# Nasceu de uma regressão real: o preenchimento de volume podava vagas até o
# volume semanal fechar, com piso por MÚSCULO (2×/semana) mas nenhum piso por
# SESSÃO. Em 5 e 6 dias o mesmo volume semanal se espalhava fino demais e saíam
# dias com 1 a 3 exercícios — cada um coerente com o alvo da semana, e nenhum
# coerente com a ideia de "um treino".
MIN_EXERCISES_PER_SESSION = 5
_SESSION_META = {v: (label, faixa, alvo) for v, label, faixa, alvo in SESSION_LENGTHS}


def valid_session_length(value: str | None) -> str | None:
    return value if value in _SESSION_META else None


def session_exercise_target(session_length: str | None) -> int | None:
    """Nº-alvo de exercícios por sessão pro tempo escolhido (None = sem escolha,
    o método usa o padrão dele)."""
    meta = _SESSION_META.get(session_length or "")
    return meta[2] if meta else None


def session_range_text(session_length: str | None) -> str | None:
    """Tempo aproximado legível (ex.: '45–60 min') ou None. É a ordem de
    grandeza da escolha; o número real do plano montado sai em `duration_note`."""
    meta = _SESSION_META.get(session_length or "")
    return meta[1] if meta else None


def effective_session_length(profile) -> str | None:
    """O tempo por sessão que REALMENTE sobra pra musculação.

    Quem respondeu "médio" mas fez essa conta incluindo cardio treina menos
    musculação do que o rótulo sugere — o tempo de peso de verdade é um degrau
    abaixo. Sem isto, `session_includes_cardio` seria só um dado guardado e
    nunca lido, a mesma falha que já derrubou `wants_cardio` e
    `known_techniques` deste arquivo."""
    bruto = valid_session_length(getattr(profile, "session_length", None))
    if bruto is None or not getattr(profile, "session_includes_cardio", False):
        return bruto
    i = _SESSION_ORDER.index(bruto)
    return _SESSION_ORDER[max(0, i - 1)]


# ---------------------------------------------------------------------------
# PERIODIZAÇÃO — o que muda de verdade é QUANDO o coach oferece deload.
# ---------------------------------------------------------------------------
# value, rótulo, descrição (o "?" de cada opção)
PERIODIZATIONS: list[tuple[str, str, str]] = [
    (
        "auto",
        "Automática",
        "O coach decide: puxa um deload quando a fadiga aparecer (a carga total começar a cair). "
        "É a recomendada pra maioria — você não precisa planejar nada.",
    ),
    (
        "linear",
        "Linear",
        "Volume fixo, só a carga sobe semana a semana. Sem deload programado: se render, sobe; se travar, "
        "a gente cuida de sono e recuperação antes de forçar. Ótima pra iniciante e intermediário.",
    ),
    (
        "ondulatoria",
        "Ondulatória",
        "Sobe volume e intensidade ao longo do mês, chegando perto do seu limite recuperável, e aí uma "
        "semana de deload pra dessensibilizar a fadiga. Rende mais, exige mais controle — pra avançado.",
    ),
]
PERIODIZATION_LABEL: dict[str, str] = {v: label for v, label, _ in PERIODIZATIONS}
PERIODIZATION_DESC: dict[str, str] = {v: desc for v, _, desc in PERIODIZATIONS}

# Ondulatória acumula ~4 semanas antes do deload planejado (um mesociclo).
MESOCYCLE_WEEKS = 4


def valid_periodization(value: str | None) -> str:
    return value if value in PERIODIZATION_LABEL else "auto"


def offer_deload(
    *, periodization: str, volume_worthy: bool, planned: bool, active_deload: bool
) -> bool:
    """A regra ÚNICA de quando o coach OFERECE deload — é o que mata o paradoxo
    (deload e "subir carga" nunca convivem).

    - linear: nunca desloada (a correção de fadiga é recuperar, não aliviar o plano).
    - ondulatória: deload PLANEJADO ao fim do mesociclo (planned) OU reativo se a carga cair.
    - automática: reativo — só quando a carga total realmente caiu (volume_worthy).
    Durante um deload já ativo, nunca reoferece.
    """
    if active_deload:
        return False
    if periodization == "linear":
        return False
    if periodization == "ondulatoria" and planned:
        return True
    return volume_worthy


def is_planned_deload(periodization: str, weeks_accumulating: float | None) -> bool:
    """Ondulatória chegou ao fim do mesociclo (acumulou o bastante) -> deload
    planejado. Nos outros modos não existe deload planejado."""
    return (
        periodization == "ondulatoria"
        and weeks_accumulating is not None
        and weeks_accumulating >= MESOCYCLE_WEEKS
    )


# ---------------------------------------------------------------------------
# PERÍODO de treino -> escolhe a TÉCNICA avançada certa.
# Início do mesociclo = acumulação (volume/densidade); fim = intensificação.
# ---------------------------------------------------------------------------
def training_period(weeks_accumulating: float | None) -> str:
    """'acumulacao' nas primeiras semanas do ciclo, 'intensificacao' depois.
    Sem dado (None), assume intensificação — já dá pra puxar a intensidade."""
    if weeks_accumulating is None:
        return "intensificacao"
    return "acumulacao" if weeks_accumulating < 3 else "intensificacao"


@dataclass(frozen=True)
class TechniqueInfo:
    """Uma técnica avançada, em texto — o que a pessoa lê pra saber fazer.
    `how_to` é também o que vira o `cue_text`/`detail` do overlay de execução
    (spec §7): a instrução de execução tem que estar em cima do exercício, não
    só numa referência que ninguém abre no meio do treino."""

    label: str
    when_to_use: str
    best_application: str
    how_to: str


# Catálogo das técnicas avançadas com que o coach trabalha. Reduzido a 5 —
# cluster-set e drop-set saíram do catálogo de SUGESTÃO do coach (continuam
# existindo como tipo de série que a pessoa escolhe na mão, ver SetType /
# techniqueSets.ts; são independentes deste catálogo). Texto e números vêm de
# uma revisão explícita do produto (2026-07-28), não são chute.
TECHNIQUES: dict[str, TechniqueInfo] = {
    "rest_pause": TechniqueInfo(
        label="Rest-pause em repetições únicas",
        when_to_use="Quando o objetivo é realizar mais repetições com uma carga alta, preservando a "
        "qualidade de cada repetição.",
        best_application="Exercícios estáveis, especialmente máquinas e compostos guiados.",
        how_to="Escolha uma carga para aproximadamente 5 repetições máximas. Faça 1 repetição, descanse "
        "10 segundos e repita. Continue nesse formato até completar 10 repetições totais. Encerre antes "
        "caso a execução se deteriore.",
    ),
    "myo_reps": TechniqueInfo(
        label="Myo-reps",
        when_to_use="Quando se deseja aumentar o estímulo com pouco tempo e pouco volume convencional.",
        best_application="Isoladores, cabos e máquinas estáveis.",
        how_to="Faça uma série de ativação de 6 repetições, próxima da falha. Descanse cerca de 10–20 "
        "segundos e realize 3 miniblocos de 2 repetições, mantendo a mesma carga e descansando 10–20 "
        "segundos entre os blocos.",
    ),
    "muscle_round": TechniqueInfo(
        label="Muscle round",
        when_to_use="Quando se busca grande densidade de trabalho e estímulo elevado com carga "
        "relativamente alta.",
        best_application="Máquinas muito estáveis e praticantes experientes.",
        how_to="Use uma carga com a qual conseguiria aproximadamente 8–10 repetições contínuas. Faça 6 "
        "blocos de 4 repetições, descansando cerca de 10 segundos entre os blocos. A falha ou quase falha "
        "deve ocorrer nos blocos finais.",
    ),
    "back_off": TechniqueInfo(
        label="Top set + back-off",
        when_to_use="Quando se quer combinar uma série pesada com uma série posterior de maior volume.",
        best_application="Supino, agachamento, remadas, desenvolvimento, leg press e máquinas compostas.",
        how_to="Após o aquecimento, faça 1 top set de 4–8 repetições em 1–2 RIR. Depois, reduza a carga "
        "em aproximadamente 8–15% e faça somente 1 série de back-off de 6–12 repetições, próxima da "
        "falha técnica.",
    ),
    "superset_antagonista": TechniqueInfo(
        label="Superset antagonista",
        when_to_use="Quando é necessário economizar tempo sem concentrar toda a fadiga no mesmo grupo "
        "muscular.",
        best_application="Bíceps + tríceps, peito + costas, extensora + flexora.",
        how_to="Faça o exercício A e, após 0–30 segundos, execute o exercício B. Depois de completar os "
        "dois, descanse 90–180 segundos antes de repetir. Trabalhe geralmente em 8–15 repetições e 1–2 RIR.",
    ),
}


def technique_info(key: str) -> TechniqueInfo | None:
    return TECHNIQUES.get(key)

# ---------------------------------------------------------------------------
# ESTRUTURA das técnicas — o que a tela de execução precisa MONTAR.
# ---------------------------------------------------------------------------
# O texto acima ensina a técnica; isto aqui é a técnica em forma de dados, pra
# ela virar séries e campos de registro de verdade na sessão ativa (spec §7) em
# vez de um aviso decorativo que a pessoa lê e ignora.
#
# `form` diz qual interface a execução monta:
#   "singles"           — N repetições AVULSAS da MESMA carga, uma de cada vez
#                          (rest-pause: não tem "bloco" nenhum, é 1 rep -> 10s
#                          -> 1 rep -> 10s..., cada toque marca UMA repetição)
#   "activation_blocks" — 1 série de ativação + N mini-sets clicáveis, cada um
#                          com VÁRIAS reps (myo-reps, muscle round: block_reps
#                          > 1, então cada bloco pode sair parcial/completo)
#   "cluster"           — blocos dentro da MESMA série, com pausa curta entre eles
#   "drop"              — série principal + quedas de carga encadeadas
#   "cue_only"          — não muda a estrutura da série (ex.: superset, que é
#                          sobre emendar DOIS exercícios, não sobre a série)
TECHNIQUE_STRUCTURES: dict[str, dict] = {
    # 10 repetições AVULSAS na mesma carga (~5RM), uma por vez, sem status de
    # bloco — uma rep só é feita ou não é. "activation_reps: 1" é a primeira
    # rep (R1); "blocks: 9, block_reps: 1" são R2..R10 (9×1 = 9 reps).
    "rest_pause": {
        "form": "singles",
        "activation_reps": 1,
        "blocks": 9,
        "block_reps": 1,
        "rest_between_blocks_s": 10,
    },
    "myo_reps": {
        # Ativação com 6 reps FIXAS e carga livre pra digitar — padrão definido
        # pro app (spec §7.1). Os 3 blocos de 2 vêm depois da ativação.
        "form": "activation_blocks",
        "activation_reps": 6,
        "blocks": 3,
        "block_reps": 2,
        "first_rest_s": 15,
        "rest_between_blocks_s": 15,
    },
    "muscle_round": {
        "form": "cluster",
        "blocks": 6,
        "block_reps": 4,
        "rest_between_blocks_s": 10,
    },
    # 1 top set pesado + 1 ÚNICA série de back-off — não é mais "2 séries retas
    # + meia extra". `drops: 1` + target_sets forçado a 1 pelo peso em
    # TECHNIQUE_SET_WEIGHT (ver per_exercise_max_with_technique) fazem a última
    # série reta virar o top set, com o back-off encadeado depois dela.
    # `drop_reps: None` deixa a pessoa digitar (a faixa 6–12 é larga demais pra
    # travar um número só).
    "back_off": {
        "form": "drop",
        "drops": 1,
        "drop_pct": 12,       # meio da faixa 8–15%
        "drop_reps": None,
        "rest_before_drop_s": 20,
    },
    "superset_antagonista": {"form": "cue_only"},
}


def technique_structure(key: str) -> dict:
    """Estrutura da técnica em dados, pra execução materializar as séries.
    Técnica desconhecida vira "cue_only" — nunca quebra a tela de treino."""
    return TECHNIQUE_STRUCTURES.get(key, {"form": "cue_only"})


# Quanto cada técnica vale em séries de trabalho EFETIVAS, pro orçamento de
# volume_landmarks.per_exercise_max_with_technique — o número vem direto do que
# o texto de TECHNIQUES já promete (rest-pause "dobra o volume", myo-reps e
# muscle round "contam como 2 séries", back-off "MEIA série extra"). Técnica
# sem multiplicador documentado vale 1 (não credita volume além do normal).
#
# back_off vale 2 por um motivo diferente dos outros: não é "dobra o volume da
# mesma série", é o PRÓPRIO PESO que faz per_exercise_max_with_technique (forma
# "drop": teto = PER_EXERCISE_MAX - peso) reduzir o exercício a 1 série reta —
# que é exatamente o top set. É essa 1 série + o back-off encadeado que forma
# o "1 top set + 1 back-off" da técnica, nunca mais que isso.
TECHNIQUE_SET_WEIGHT: dict[str, float] = {
    "rest_pause": 2,
    "myo_reps": 2,
    "muscle_round": 2,
    "back_off": 2,
    "superset_antagonista": 1,
}


# --- QUANTO TEMPO CADA TÉCNICA CUSTA ---------------------------------------
# Uma técnica que vale 2 séries substitui 2 séries retas. A pergunta que
# importa numa sessão curta é: ela leva MENOS tempo que as 2 retas que
# substitui?
#
# A conta sai dos próprios dados de TECHNIQUE_STRUCTURES (repetições × segundos
# por repetição + os descansos declarados), então ela não pode divergir do que a
# tela de execução materializa. Mexer numa estrutura muda o número aqui junto —
# que é o ponto: já houve uma vez em que muscle round passou a 6 blocos e a
# conclusão sobre tempo ficou desatualizada num comentário.
SEGUNDOS_POR_REP = 3
# A referência: 2 séries retas de 10 reps com 90s de descanso entre elas.
_REPS_SERIE_RETA = 10
_DESCANSO_ENTRE_RETAS_S = 90


def technique_seconds(key: str) -> int | None:
    """Segundos que a técnica leva, incluindo os descansos internos. None quando
    a técnica não muda a série (superset é só uma dica de execução)."""
    st = technique_structure(key)
    forma = st.get("form")
    if forma == "activation_blocks":
        reps = st["activation_reps"] + st["blocks"] * st["block_reps"]
        descanso = st.get("first_rest_s", 0) + st["rest_between_blocks_s"] * st["blocks"]
    elif forma == "singles":
        reps = st["activation_reps"] + st["blocks"] * st["block_reps"]
        descanso = st["rest_between_blocks_s"] * st["blocks"]
    elif forma == "cluster":
        reps = st["blocks"] * st["block_reps"]
        descanso = st["rest_between_blocks_s"] * st["blocks"]
    elif forma == "drop":
        reps = _REPS_SERIE_RETA + 8  # a reta pesada + o back-off encurtado
        descanso = st.get("rest_before_drop_s", 0)
    else:
        return None
    return reps * SEGUNDOS_POR_REP + descanso


def technique_time_saved_s(key: str) -> int | None:
    """Segundos POUPADOS pela técnica contra as séries retas que ela substitui.
    Positivo = mais rápida. None quando não se aplica."""
    custo = technique_seconds(key)
    if custo is None:
        return None
    equivalentes = TECHNIQUE_SET_WEIGHT.get(key, 1)
    retas = equivalentes * _REPS_SERIE_RETA * SEGUNDOS_POR_REP + (
        max(0, equivalentes - 1) * _DESCANSO_ENTRE_RETAS_S
    )
    return int(retas - custo)


# Fallback por (composto?, período) pro caso "meio-termo" (tempo médio/não
# definido, sem ser ponto fraco): acumulação puxa densidade/volume,
# intensificação puxa intensidade — o resto do critério é session_length e
# ponto fraco, tratados em suggest_technique. Composto+acumulação usa muscle
# round (mesma lógica de "densidade com carga relativamente alta" que o
# catálogo já atribui a ela) — só isolado+intensificação usa muscle round
# também, o que é intencional: a técnica serve pros dois casos.
_TECH_BY_PERIOD: dict[tuple[bool, str], str] = {
    (True, "acumulacao"): "muscle_round",
    (True, "intensificacao"): "rest_pause",
    (False, "acumulacao"): "myo_reps",
    (False, "intensificacao"): "muscle_round",
}


def advanced_allowed(profile) -> bool:
    """A pessoa aceita técnica avançada (myo-reps, rest-pause, muscle round)?

    Regra de segurança quando ela nunca respondeu (perfil antigo, `None`):
    INICIANTE não recebe. Quem está no primeiro ou segundo ano precisa de
    execução e constância, não de intensificação — a fadiga extra atrapalha
    mais do que ajuda, e a progressão ainda vem sozinha da carga.

    Dito "não", o coach fica só com série normal: sem dica de técnica na
    prévia do treino, sem finisher com técnica no montador, e o endpoint de
    aplicar técnica recusa. Volume e carga continuam progredindo igual.
    """
    if profile is None:
        return False
    escolha = getattr(profile, "allow_advanced_techniques", None)
    if escolha is not None:
        return bool(escolha)
    nivel = getattr(profile, "experience_level", None)
    nivel = getattr(nivel, "value", nivel)
    return nivel != "iniciante"


# ---------------------------------------------------------------------------
# AUDITORIA DA TÉCNICA (Cap. XVII) — antes de aplicar, o exercício aguenta?
# ---------------------------------------------------------------------------
# O Cap. XIII diz COMO escolher a técnica; o XVII manda AUDITAR antes de aplicar
# e decidir entre autorizar, ajustar ou rejeitar. Faltava a auditoria: o motor
# escolhia por período/tempo/ponto fraco e aplicava, sem nunca perguntar se
# aquele exercício suportava aquela técnica.
#
# O manual é específico sobre onde técnica de INTENSIFICAÇÃO pode entrar
# ("máquinas, cabos, exercícios guiados, com apoio, altamente estáveis, com
# interrupção segura") e onde não pode ("exercícios livres pesados, de elevada
# complexidade técnica, com grande carga axial, em que uma repetição falhada
# represente risco, em que estabilizadores ou capacidade cardiovascular sejam os
# principais limitantes").
#
# Rest-pause, myo-reps e muscle round são todas de intensificação: trabalham
# perto da falha com pausas curtas. Back-off e superset são de ORGANIZAÇÃO (de
# carga e de tempo) e o manual as libera em peso livre — "a aplicação depende da
# segurança e da competência técnica, não apenas da categoria do exercício".
TECNICAS_DE_INTENSIFICACAO = frozenset({"rest_pause", "myo_reps", "muscle_round"})


def technique_audit(taxon, technique_key: str) -> str | None:
    """None quando a técnica está autorizada nesse exercício; senão, o MOTIVO da
    rejeição, em texto (Cap. XVII Partes C e E).

    O motivo volta em texto e não como booleano porque quem chama precisa saber
    o que oferecer no lugar — e porque um "não" sem motivo é exatamente o tipo de
    decisão silenciosa que este projeto já pagou caro pra tirar do motor.
    """
    from app.ai.exercise_taxonomy import Limiter, Stability, Systemic

    if technique_key not in TECNICAS_DE_INTENSIFICACAO:
        return None  # back-off e superset organizam carga/tempo, não intensificam

    if taxon.stability is Stability.BAIXA:
        return ("o exercício depende de equilíbrio, e a técnica exige chegar perto da falha "
                "com a execução ainda inteira")
    if taxon.systemic is Systemic.ALTO:
        return ("o exercício tem carga axial e demanda neural altas — falhar uma repetição "
                "aqui é risco, não estímulo")
    if taxon.limiter in (Limiter.ESTABILIZADORES, Limiter.CARDIO, Limiter.LOMBAR):
        return (f"quem encerra a série nesse exercício é {taxon.limiter.value}, não o músculo — "
                "a técnica só ia acumular fadiga onde ela não vira estímulo")
    return None


def suggest_technique(
    is_compound: bool,
    period: str,
    *,
    session_length: str | None = None,
    is_weak_point: bool = False,
) -> tuple[str, str, str]:
    """(chave, rótulo, como-fazer) da técnica certa pra um exercício travado.
    Determinístico: a barra do coach e o endpoint que aplica rederivam daqui e
    sempre concordam. Prioridade das regras:

    1) PONTO FRACO — rest-pause é a técnica certa pra atacar um grupo que a
       pessoa priorizou: dobra o volume efetivo da série (~10 reps numa carga
       de ~4-5RM), com o cuidado de fadiga que isso pede. Ele ganha do critério
       de tempo (item 2) mesmo numa sessão curta, e isso não custa tempo:
       rest-pause também é mais rápido que as 2 séries retas que substitui (ver
       `technique_time_saved_s`, coberto por teste). Prioridade e pressa não
       estão em conflito aqui — o que seria um problema é o coach escolher, num
       treino curto, uma técnica que ESTICA a sessão.
    2) POUCO TEMPO por sessão — MYO-REPS, tanto no composto quanto no isolado.
       Hipertrofia é volume-dependente, e fragmentar a série acumula volume sem
       esticar o treino. Antes o composto levava muscle round aqui; virou
       myo-reps por medição: myo-reps economiza ~80s por exercício contra as
       séries retas equivalentes, enquanto muscle round com 6 blocos CUSTA ~20s.
       Numa sessão curta o que se quer é justamente o tempo, então a técnica que
       poupa é a certa. (Muscle round continua sendo a escolha de acumulação no
       item 4, onde o critério é densidade e não tempo.)
    3) BASTANTE TEMPO por sessão — back-off testa a tolerância a uma camada
       extra de volume ANTES de comprometer com uma série reta a mais no
       treino (não é permanente, é o teste).
    4) Meio-termo (tempo médio/não definido, sem ser ponto fraco) — a fase do
       ciclo decide: acumulação puxa densidade/volume, intensificação puxa
       intensidade (fallback por período, como antes).
    """
    is_compound = bool(is_compound)
    if is_weak_point:
        key = "rest_pause"
    elif session_length == "curto":
        key = "myo_reps"
    elif session_length == "longo":
        key = "back_off"
    else:
        key = _TECH_BY_PERIOD.get((is_compound, period)) or ("rest_pause" if is_compound else "myo_reps")
    info = TECHNIQUES[key]
    return key, info.label, info.how_to


# ---------------------------------------------------------------------------
# INTENÇÃO DE SÉRIE — quando o coach monta a rotina, marca qual das séries de
# TRABALHO é "até a falha" (bate com o SetType TO_FAILURE do app). Aquecimento
# e feeder NÃO entram aqui: são preparação (rampa calculada a partir da carga
# de trabalho, regra 5), aparecem ANTES da Série 1 e não consomem um slot de
# target_sets — ver warmup_feeder_ramp_for. As demais posições ficam None =
# série reta normal, sem opinião.
# ---------------------------------------------------------------------------
def set_intents_for(target_sets: int, is_compound: bool) -> list[str | None]:
    """Lista do tamanho de target_sets com a intenção de cada série de trabalho:

    - 1 série só (HIT-style: DC/Mentzer) -> ela é a série, então "até a falha"
      — é literalmente a filosofia dessas metodologias.
    - 2+ séries -> só a última vira "até a falha"; as demais ficam normais
      (série reta, RIR sugerido por suggested_work_rir).
    """
    if target_sets <= 0:
        return []
    if target_sets == 1:
        return ["to_failure"]
    intents: list[str | None] = [None] * target_sets
    intents[-1] = "to_failure"
    return intents


def suggested_work_rir(period: str) -> int:
    """RIR sugerido pra uma série de trabalho reta (nem aquecimento/feeder,
    nem até a falha — essa fica sempre em RIR 0). Faixa recomendada é 2 a 0
    RIR; só na fase de intensificação (perto do topo do mesociclo/MVR) vale
    puxar pra 1 a 0 RIR — falha total só quando a pessoa realmente não
    conseguir mais uma repetição, não um chute."""
    return 1 if period == "intensificacao" else 2


# ---------------------------------------------------------------------------
# AQUECIMENTO + FEEDER — TODO exercício tem exatamente uma série de aquecimento
# e uma de feeder na frente, calculadas a partir da carga REAL (a mais pesada
# entre as séries de trabalho/falha do exercício, não um chute). Nenhuma das
# duas conta no número de séries do título/log book — é preparação, não
# trabalho (regra 5). O feeder NÃO é rampa: é uma única série a 50%.
# ---------------------------------------------------------------------------
def warmup_feeder_ramp_for(
    base_weight_kg: float | None,
    *,
    include_warmup: bool = True,
    include_feeder: bool = True,
) -> list[dict]:
    """Aquecimento (25% da carga, 12–15 reps) + feeder (50% da carga, 8–10
    reps). `base_weight_kg` é a carga mais pesada entre as séries de trabalho
    e de falha do exercício (o mais pesado entre os dois). Sem histórico, o
    peso vem None e a pessoa preenche na mão.

    `include_warmup=False` quando o grupo/padrão JÁ foi preparado antes na
    mesma sessão (§6.3): tríceps depois do supino não precisa de aquecimento
    geral de novo — repetir isso só rouba tempo e energia do treino.
    `include_feeder` continua valendo mesmo com o músculo aquecido, quando o
    exercício é pesado ou tem um padrão bem diferente (série de aproximação).
    """

    def _round(kg: float) -> float | None:
        return round(kg * 2) / 2 if kg else None  # incremento de 0.5kg

    base = base_weight_kg if base_weight_kg and base_weight_kg > 0 else None
    out: list[dict] = []
    if include_warmup:
        out.append({"kind": "warmup", "label": "Aquecimento",
                    "weight_kg": _round(base * 0.25) if base else None,
                    "reps_min": 12, "reps_max": 15})
    if include_feeder:
        out.append({"kind": "feeder", "label": "Feeder",
                    "weight_kg": _round(base * 0.50) if base else None,
                    "reps_min": 8, "reps_max": 10})
    return out


# ---------------------------------------------------------------------------
# QUEM PREPARA QUEM (§6.3). Ao treinar o músculo-chave, estes já entram
# aquecidos junto e não pedem aquecimento próprio depois na mesma sessão.
#
# A tabela da spec é explícita e tem uma assimetria de propósito:
#   supino  -> tríceps e ombro JÁ aquecidos  (empurrar carrega os dois)
#   remada  -> bíceps NÃO                    (rosca é o primeiro trabalho
#                                             direto específico de bíceps)
# ---------------------------------------------------------------------------
_PREPARA: dict[MuscleGroup, tuple[MuscleGroup, ...]] = {
    MuscleGroup.CHEST: (MuscleGroup.TRICEPS, MuscleGroup.SHOULDERS),
    MuscleGroup.SHOULDERS: (MuscleGroup.TRICEPS,),
    MuscleGroup.TRICEPS: (),
    # Costas prepara costas e trapézio; bíceps continua pedindo o dele.
    MuscleGroup.BACK: (MuscleGroup.TRAPS,),
    MuscleGroup.BICEPS: (MuscleGroup.FOREARMS,),
    # Mesma lógica nas pernas: agachar/levantar já prepara glúteo e posterior.
    MuscleGroup.QUADS: (MuscleGroup.GLUTES, MuscleGroup.HAMSTRINGS),
    MuscleGroup.HAMSTRINGS: (MuscleGroup.GLUTES,),
    MuscleGroup.GLUTES: (),
}


def prepared_by(muscle: MuscleGroup) -> tuple[MuscleGroup, ...]:
    """Músculos que ficam prontos de carona ao treinar `muscle`."""
    return (muscle,) + _PREPARA.get(muscle, ())


def needs_warmup(
    primary_muscle: MuscleGroup, already_prepared: set[MuscleGroup]
) -> bool:
    """Este exercício abre o trabalho desse grupo na sessão? Só nesse caso o
    aquecimento geral entra (§6.3)."""
    return primary_muscle not in already_prepared


def needs_feeder(is_compound: bool, warmed: bool) -> bool:
    """Feeder é diferente de aquecimento e continua existindo mesmo com o
    músculo quente: um exercício PESADO (composto) merece uma série de
    aproximação antes da série valendo. Isolado com o músculo já preparado vai
    direto pro trabalho."""
    return True if not warmed else is_compound
