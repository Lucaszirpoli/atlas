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
# título + texto — então não depende disso.
TECHNIQUES: dict[str, tuple[str, str]] = {
    "rest_pause": (
        "Rest-pause",
        "Na última série valendo: chegue à falha técnica, descanse 15–20s e faça mais reps com a MESMA "
        "carga. Repita 1–2 micro-séries. Extrai mais estímulo de um composto sem adicionar séries.",
    ),
    "cluster_set": (
        "Cluster (séries fragmentadas)",
        "Quebre a série em blocos: 2–4 reps, 15–20s de descanso DENTRO da série, e repita até somar o "
        "total (ex.: 4×3). Mantém a carga alta com técnica limpa — ideal pra intensificar um composto.",
    ),
    "myo_reps": (
        "Myo-reps",
        "Uma série de ativação até perto da falha (12–20 reps), descanse ~5 respirações e faça mini-séries "
        "de 3–5 reps repetindo o descanso curto, até não fechar mais. Muito volume efetivo em pouco tempo.",
    ),
    "muscle_round": (
        "Muscle round",
        "Carga de ~6RM: faça séries de 4 reps com 10–15s de descanso entre elas, somando ~6 rounds "
        "(24 reps no total). Densidade alta com a mesma carga — um choque de hipertrofia no isolado.",
    ),
    "back_off": (
        "Back-off",
        "Depois da série pesada no topo da faixa, tire 15–20% da carga e faça 1–2 séries de reps altas "
        "(12–20). Aproveita a ativação da pesada e acumula volume sem fritar a articulação.",
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

# Escolha por (composto?, período). Acumulação puxa densidade/volume;
# intensificação puxa intensidade. Assim a técnica combina com a fase do ciclo.
_TECH_BY_PERIOD: dict[tuple[bool, str], str] = {
    (True, "acumulacao"): "cluster_set",
    (True, "intensificacao"): "rest_pause",
    (False, "acumulacao"): "myo_reps",
    (False, "intensificacao"): "muscle_round",
}


def suggest_technique(is_compound: bool, period: str) -> tuple[str, str, str]:
    """(chave, rótulo, como-fazer) da técnica certa pra um exercício, conforme
    ser composto/isolado e o período do ciclo. Determinístico: a barra do coach
    e o endpoint que aplica rederivam daqui e sempre concordam."""
    key = _TECH_BY_PERIOD.get((bool(is_compound), period)) or (
        "rest_pause" if is_compound else "drop_set"
    )
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
