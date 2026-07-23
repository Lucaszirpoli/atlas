"""O 'cérebro de treino' do Coaching.

Centraliza, num lugar só e SEM IA, as preferências de treino da pessoa (ponto
fraco, tempo por sessão, cardio, periodização) e as REGRAS que elas disparam:
qual técnica avançada usar em cada período, e quando o coach oferece deload
conforme a periodização escolhida.

Tudo determinístico e à vista, como o resto do coach — o mesmo input sempre gera
o mesmo output. A camada de conversa (IA Pro) só traduz isto; não muda a decisão.
"""

from __future__ import annotations

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


# Quantos pontos fracos a pessoa pode priorizar de uma vez. Dois é o teto: mais
# que isso deixa de ser "ponto fraco" e vira o treino inteiro.
WEAK_POINTS_MAX = 2


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


# ---------------------------------------------------------------------------
# DIAS por semana que a pessoa pode treinar (2–7). É o que define quantos
# treinos o coach monta. None = automático (infere dos dias do onboarding).
# ---------------------------------------------------------------------------
TRAINING_DAYS_MIN = 2
TRAINING_DAYS_MAX = 7
TRAINING_DAYS_OPTIONS: list[int] = list(range(TRAINING_DAYS_MIN, TRAINING_DAYS_MAX + 1))


def valid_training_days(value: int | None) -> int | None:
    """None (automático) ou um inteiro dentro de 2–7; fora disso vira None."""
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
# value, rótulo, faixa de tempo, exercícios-alvo por sessão
SESSION_LENGTHS: list[tuple[str, str, str, int]] = [
    ("curto", "Curto", "45–70 min", 5),
    ("medio", "Médio", "70–100 min", 6),
    ("longo", "Longo", "100–120 min", 8),
]
_SESSION_META = {v: (label, faixa, alvo) for v, label, faixa, alvo in SESSION_LENGTHS}


def valid_session_length(value: str | None) -> str | None:
    return value if value in _SESSION_META else None


def session_exercise_target(session_length: str | None) -> int | None:
    """Nº-alvo de exercícios por sessão pro tempo escolhido (None = sem escolha,
    o método usa o padrão dele)."""
    meta = _SESSION_META.get(session_length or "")
    return meta[2] if meta else None


def session_range_text(session_length: str | None) -> str | None:
    """Faixa de tempo legível (ex.: '45–70 min') ou None."""
    meta = _SESSION_META.get(session_length or "")
    return meta[1] if meta else None


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


# Catálogo das técnicas avançadas com que o coach trabalha. chave -> (rótulo,
# como-fazer). As chaves batem com o enum SetType quando existe (rest_pause,
# drop_set, myo_reps, cluster_set), mas aqui a dica é overlay de execução —
# título + texto — então não depende disso. Os números e o jeito de contar no
# log book vêm de definição direta do produto (não são chute): cada técnica
# tem uma regra explícita de "quanto conta como série", pra bater com o volume
# real que ela entrega.
TECHNIQUES: dict[str, tuple[str, str]] = {
    "rest_pause": (
        "Rest-pause",
        "Carga de ~4–5RM: faça 1 repetição por vez, com 10–15s de descanso entre elas, até somar ~10 reps "
        "no total — dobra o volume efetivo dessa série. Como as reps ficam sempre perto da falha, gerencie "
        "bem a fadiga: é pontual, não pra toda sessão.",
    ),
    "cluster_set": (
        "Cluster (séries fragmentadas)",
        "Quebre a série em blocos: 2–4 reps, 15–20s de descanso DENTRO da série, e repita até somar o "
        "total (ex.: 4×3). Mantém a carga alta com técnica limpa — ideal pra intensificar um composto.",
    ),
    "myo_reps": (
        "Myo-reps",
        "Série de ativação: 6 reps a 0 RIR (conta como 1 série no log book). Descanse 30–40s e faça um "
        "bloco de 2 reps; descanse ~20s e repita até fechar 3 blocos de 2 (ativação + 2/2/2). O conjunto "
        "inteiro conta como 2 séries — acumula volume de verdade num treino curto, sem esticar a sessão.",
    ),
    "muscle_round": (
        "Muscle round",
        "Escolha uma carga de ~8RM e fragmente em blocos de 4 reps, com 15–20s de descanso entre eles — "
        "no mínimo 4 blocos, no máximo 6 (16–24 reps no total). Um muscle round completo conta como 2 "
        "séries no log book, sempre (não triplica mesmo fechando os 6 blocos). Mesma ideia do myo-reps: "
        "volume eficiente em pouco tempo.",
    ),
    "back_off": (
        "Back-off",
        "Depois de 2 séries retas, descanse 30s, tire ~30% da carga e faça mais 8 reps. Conta como MEIA "
        "série extra no log book — é um teste de tolerância a mais volume antes de comprometer com uma "
        "série reta a mais de verdade.",
    ),
    "superset_antagonista": (
        "Superset antagonista",
        "Emende o exercício com um do músculo oposto (peito↔costas, bíceps↔tríceps, quadríceps↔posterior) "
        "sem descanso entre eles. Ganha densidade e um ajuda a recuperação do outro, sem perder carga.",
    ),
    "drop_set": (
        "Drop-set",
        "Na última série: ao falhar, tire ~20–30% da carga e siga sem descanso até falhar de novo. "
        "Um choque de volume pra destravar o isolado.",
    ),
}

# Fallback por (composto?, período) pro caso "meio-termo" (tempo médio/não
# definido, sem ser ponto fraco): acumulação puxa densidade/volume,
# intensificação puxa intensidade — o resto do critério é session_length e
# ponto fraco, tratados em suggest_technique.
_TECH_BY_PERIOD: dict[tuple[bool, str], str] = {
    (True, "acumulacao"): "cluster_set",
    (True, "intensificacao"): "rest_pause",
    (False, "acumulacao"): "myo_reps",
    (False, "intensificacao"): "muscle_round",
}


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
       de ~4-5RM), com o cuidado de fadiga que isso pede.
    2) POUCO TEMPO por sessão — hipertrofia é volume-dependente, então
       fragmentar a série (myo-reps/muscle round) acumula volume de verdade
       sem esticar um treino curto. Composto -> muscle round; isolado -> myo-reps.
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
        key = "muscle_round" if is_compound else "myo_reps"
    elif session_length == "longo":
        key = "back_off"
    else:
        key = _TECH_BY_PERIOD.get((is_compound, period)) or ("rest_pause" if is_compound else "drop_set")
    label, cue = TECHNIQUES[key]
    return key, label, cue


# ---------------------------------------------------------------------------
# CARDIO — sem cardio pode faltar pro objetivo; o coach avisa (não obriga).
# ---------------------------------------------------------------------------
def cardio_warning(goal: str | None, wants_cardio: bool | None) -> str | None:
    """Aviso quando a pessoa optou por treinar SEM cardio e o objetivo se
    beneficiaria dele. None quando não escolheu (None) ou escolheu com cardio."""
    if wants_cardio is not False:
        return None
    if goal in {"emagrecimento", "performance"}:
        return (
            "Você escolheu treinar sem cardio. Pro seu objetivo o cardio ajuda bastante — sem ele, o gasto "
            "calórico fica todo por conta da dieta e do seu dia a dia (passos/NEAT). Dá pra ir sem, mas o "
            "coach vai cobrar mais precisão na comida e no movimento fora do treino."
        )
    return None


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
def warmup_feeder_ramp_for(base_weight_kg: float | None) -> list[dict]:
    """Aquecimento (25% da carga, 12–15 reps) + feeder (50% da carga, 8–10
    reps). `base_weight_kg` é a carga mais pesada entre as séries de trabalho
    e de falha do exercício (o mais pesado entre os dois). Sempre retorna as
    duas séries — na primeira vez no exercício ainda não há carga pra basear
    o peso, então weight_kg vem None e a pessoa preenche na mão (mesmo padrão
    das séries de trabalho sem histórico)."""

    def _round(kg: float) -> float | None:
        return round(kg * 2) / 2 if kg else None  # incremento de 0.5kg

    base = base_weight_kg if base_weight_kg and base_weight_kg > 0 else None
    return [
        {"kind": "warmup", "label": "Aquecimento",
         "weight_kg": _round(base * 0.25) if base else None,
         "reps_min": 12, "reps_max": 15},
        {"kind": "feeder", "label": "Feeder",
         "weight_kg": _round(base * 0.50) if base else None,
         "reps_min": 8, "reps_max": 10},
    ]
