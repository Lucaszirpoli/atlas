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
        key = _TECH_BY_PERIOD.get((is_compound, period)) or ("rest_pause" if is_compound else "myo_reps")
    info = TECHNIQUES[key]
    return key, info.label, info.how_to


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
