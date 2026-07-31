"""Motor DETERMINÍSTICO de montagem de treino, guiado pela REGRA MESTRA.

Recebe uma MethodSpec (os números da sessão: reps, RIR, descanso) + o perfil da
pessoa, e monta o treino da semana preenchendo os BLUEPRINTS de sessão
(`session_blueprints`): cada dia é uma sequência explícita de vagas, e cada vaga
declara o papel que cumpre, o padrão de movimento e a região muscular.

O que o motor decide é só QUAL exercício entra em cada vaga, e ele decide por
regra, não por sorteio:

  1. TIER (Princípio 2 / regra de substituição). Tier S primeiro, sempre. Só
     desce pra A, depois B, depois C quando não sobrou opção — e nunca "porque
     deu na veneta": desce porque o tier de cima acabou.
  2. FUNÇÃO ÚNICA (Princípio 4). Duas vagas do mesmo dia não recebem exercícios
     de mesma função (padrão + região). É o que impede supino reto barra +
     supino reto Smith + chest press no mesmo treino.
  3. VARIAÇÃO NA SEMANA. Exercício já usado em outro dia só volta quando o pool
     fresco acabou — aí é melhor repetir um bom exercício do que deixar a vaga
     vazia ou raspar um tier C.
  4. PREFERÊNCIA DA PESSOA. Máquinas x peso livre, evitar agachamento livre /
     acima da cabeça / impacto, priorizar unilateral. Exclusão vira filtro;
     preferência vira ordenação.

`validate_plan` é a "Regra de coerência global": roda antes de entregar e
reprova o treino que fura cobertura, equilíbrio ou ordem — ver o módulo
`plan_review`, que é quem faz as perguntas.

A montagem é determinística: mesma entrada, mesmo treino. Só usa exercício que
existe na base (o motor nunca inventa exercício).
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import session_blueprints as bp
from app.ai.exercise_taxonomy import (
    ORDER_MINOR,
    REQUIRED_REGIONS,
    Pattern,
    Taxon,
    order_class_for_pattern,
    taxon_for_exercise,
    tier_rank,
)
from app.ai.methods import MethodSpec, coach_split_for
from app.core.text import normalize_search_text
from app.models.exercise import (
    STRENGTH_CATEGORIES,
    Equipment,
    Exercise,
    MuscleGroup,
    quality_order,
)

# Preferências de exercício que a pessoa marcou no questionário
# (training_brain.EXERCISE_PREFS). Cada uma vira EXCLUSÃO ou PRIORIDADE aqui —
# é o que faz "prefiro máquinas e exercícios estáveis" mudar o treino de
# verdade, em vez de virar um texto que ninguém lê.
_PREF_EXCLUI = {
    # Agachamento COM BARRA nas costas. Leg press, hack e agachamento em
    # máquina continuam valendo — a queixa é a barra nas costas, não o padrão.
    "sem_agachamento_livre": ("agachamento livre", "agachamento com barra", "back squat", "front squat"),
    "sem_acima_da_cabeca": (
        "desenvolvimento", "militar", "overhead", "acima da cabeca", "elevacao frontal com barra",
    ),
    "sem_impacto": ("salto", "pulo", "jump", "corrida", "burpee", "pliometr", "box jump"),
}
_PREF_UNILATERAL = ("unilateral", "um braco", "uma perna", "afundo", "avanco", "bulgaro", "serrote", "alternado")

_ESTAVEIS = (Equipment.MACHINE, Equipment.CABLE, Equipment.SMITH_MACHINE)
_LIVRES = (Equipment.BARBELL, Equipment.DUMBBELL, Equipment.KETTLEBELL)

# Quantos candidatos EQUIVALENTES entram no sorteio de variação por pessoa.
#
# Duas pessoas que respondem exatamente a mesma coisa no questionário recebiam
# exatamente o mesmo treino, exercício por exercício — o motor é determinístico e
# o desempate final era a ordem de qualidade, que é global. O treino estava
# certo, mas não parecia dela.
#
# A variação não pode custar qualidade: o sorteio acontece só DENTRO da classe de
# equivalência (mesmo tier, mesma aderência às preferências da pessoa, mesma
# função), e ainda assim só entre os `_POOL_VARIACAO` melhores por ordem de
# qualidade. Ninguém troca um tier S consagrado por um tier S obscuro sem GIF —
# a escolha continua sendo entre opções que a regra considera igualmente boas.
_POOL_VARIACAO = 3


def _sorteio_estavel(seed: int, *partes: object) -> int:
    """Número estável a partir da semente + identificadores da vaga.

    blake2b em vez de `hash()`: o hash de string do Python é aleatorizado por
    processo (PYTHONHASHSEED), o que faria o treino da MESMA pessoa mudar a cada
    reinício do servidor. Aqui a mesma entrada dá sempre o mesmo número — em
    qualquer máquina, em qualquer deploy.
    """
    texto = "|".join(str(p) for p in (seed, *partes))
    return int.from_bytes(hashlib.blake2b(texto.encode("utf-8"), digest_size=8).digest(), "big")


def _escolher_com_variacao(
    ordenados: list[_Cand], equivalencia, seed: int | None, *partes: object
) -> _Cand:
    """O melhor candidato — com sorteio por pessoa entre os que empatam com ele.

    `ordenados` já vem na ordem de decisão do motor (tier -> preferências ->
    qualidade). Sem semente, devolve o primeiro: é o comportamento determinístico
    de sempre, que os testes de estrutura dependem.
    """
    melhor = ordenados[0]
    if seed is None:
        return melhor
    chave = equivalencia(melhor)
    empatados = [c for c in ordenados if equivalencia(c) == chave][:_POOL_VARIACAO]
    if len(empatados) < 2:
        return melhor
    return min(empatados, key=lambda c: _sorteio_estavel(seed, *partes, c.ex.name))


def _ordenar_por_preferencia(nome_norm: str, equipamento, prefs: frozenset[str]) -> int:
    """Peso de ordenação (menor = mais cedo) pelas preferências da pessoa.
    Só REORDENA — nunca deixa a vaga sem exercício."""
    peso = 0
    if "maquinas" in prefs:
        peso += 0 if equipamento in _ESTAVEIS else 2
    elif "peso_livre" in prefs:
        peso += 0 if equipamento in _LIVRES else 2
    if "unilateral" in prefs:
        peso += 0 if any(k in nome_norm for k in _PREF_UNILATERAL) else 1
    return peso


def _proibido_por_preferencia(nome_norm: str, prefs: frozenset[str]) -> bool:
    """True quando o exercício bate numa preferência de EVITAR."""
    return any(
        chave in prefs and any(k in nome_norm for k in palavras)
        for chave, palavras in _PREF_EXCLUI.items()
    )


@dataclass
class PlannedSlot:
    order: int
    muscle_group: str
    is_compound: bool
    exercise_id: int | None
    exercise_name: str
    sets: str
    reps: str
    tempo: str | None
    rest_seconds: str | None
    rir: str | None
    note: str | None = None
    # Vocabulário da regra mestra. `note` carrega o papel em texto (é o que a
    # pessoa lê na rotina); estes dois são pro validador e pro motor.
    pattern: str | None = None
    region: str | None = None
    role: str | None = None
    # Abre a sessão por PRIORIDADE (ponto fraco / dia de membros) em vez de por
    # ser o movimento mais pesado. Ver `session_blueprints.SlotSpec.opener`.
    priority_opener: bool = False


@dataclass
class PlannedSession:
    day_index: int
    day_label: str
    focus: str
    phase_name: str | None
    slots: list[PlannedSlot] = field(default_factory=list)


@dataclass
class WorkoutPlan:
    method_key: str
    method_name: str
    author: str
    days_per_week: int
    mesocycle: str | None
    deload_rule: str | None
    progression_rule: str
    phase_context: str | None
    sessions: list[PlannedSession] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def resolve_days(method: MethodSpec, available_days: int | None) -> int:
    """Casa a disponibilidade da pessoa com as frequências suportadas — o maior
    nº suportado que não passa da disponibilidade."""
    supported = sorted(method.days_per_week) or [3]
    if available_days is None:
        return supported[0]
    feasible = [d for d in supported if d <= available_days]
    return feasible[-1] if feasible else supported[0]


# ---------------------------------------------------------------------------
# Pool de candidatos
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Cand:
    """Um exercício da base + sua taxonomia, já resolvidos juntos."""

    ex: Exercise
    taxon: Taxon
    nome_norm: str
    qualidade: int  # posição na ordenação de qualidade (menor = melhor)


def _load_pool(db: Session) -> list[_Cand]:
    """TODOS os exercícios visíveis de musculação, uma consulta só.

    A biblioteca curada tem ~119 linhas, então carregar tudo e decidir em Python
    é mais rápido (e muito mais legível) do que uma consulta por vaga — e é o
    que permite a taxonomia, que vive em Python, mandar na escolha.
    """
    stmt = (
        select(Exercise)
        .where(
            Exercise.is_custom.is_(False),
            Exercise.is_hidden.is_(False),
            # Só musculação: sem isto a base devolvia alongamento e mobilidade
            # como se fossem exercício de rotina.
            Exercise.category.in_(STRENGTH_CATEGORIES),
        )
        .order_by(*quality_order())
    )
    return [
        _Cand(ex, taxon_for_exercise(ex), normalize_search_text(ex.name), i)
        for i, ex in enumerate(db.execute(stmt).scalars())
    ]


# REGRA DE SUBSTITUIÇÃO (a da spec, item 1-3): quando a base não tem NADA que
# preencha a vaga — porque a preferência da pessoa excluiu tudo, ou porque a
# biblioteca não cobre aquele padrão pra aquele músculo — a vaga não pode
# simplesmente desaparecer. Estes são os substitutos que "preservam o mesmo
# objetivo mecânico" e mantêm o equilíbrio da sessão.
#
# O caso que motivou: quem marca "evitar exercícios acima da cabeça" perde TODO
# desenvolvimento, então a vaga de empurrar vertical do superior B ficava vazia —
# a sessão saía com 6 exercícios e a semana com 2 empurradas a menos que
# puxadas, e o validador reprovava um treino que era só consequência de uma
# preferência legítima. A substituição certa é a que um treinador faria: se não
# pode empurrar acima da cabeça, empurra na horizontal.
_SUBSTITUTO: dict[tuple[Pattern, MuscleGroup], tuple[Pattern, MuscleGroup]] = {
    (Pattern.PUSH_V, MuscleGroup.SHOULDERS): (Pattern.PUSH_H, MuscleGroup.CHEST),
    (Pattern.PUSH_H, MuscleGroup.CHEST): (Pattern.PUSH_V, MuscleGroup.SHOULDERS),
    (Pattern.PULL_V, MuscleGroup.BACK): (Pattern.PULL_H, MuscleGroup.BACK),
    (Pattern.PULL_H, MuscleGroup.BACK): (Pattern.PULL_V, MuscleGroup.BACK),
    # Perna: quem não pode agachar faz extensora; quem não pode dobradiça de
    # quadril faz flexora (e vice-versa) — continua sendo posterior.
    (Pattern.KNEE, MuscleGroup.QUADS): (Pattern.ISO, MuscleGroup.QUADS),
    (Pattern.HIP, MuscleGroup.HAMSTRINGS): (Pattern.KNEE_FLEX, MuscleGroup.HAMSTRINGS),
    (Pattern.KNEE_FLEX, MuscleGroup.HAMSTRINGS): (Pattern.HIP, MuscleGroup.HAMSTRINGS),
    (Pattern.HIP, MuscleGroup.GLUTES): (Pattern.ISO, MuscleGroup.GLUTES),
}


def _substituto(spec: bp.SlotSpec) -> bp.SlotSpec | None:
    """A vaga equivalente, quando a original não tem candidato. Sem região
    exigida (a substituição já é o plano B — cobrar região por cima dela deixaria
    a vaga vazia de novo) e aceitando repetir função."""
    alvo = _SUBSTITUTO.get((spec.pattern, spec.muscle))
    if alvo is None:
        return None
    padrao, musculo = alvo
    return bp.SlotSpec(
        role=spec.role,
        pattern=padrao,
        muscle=musculo,
        region=None,
        priority=spec.priority,
        allow_repeat_function=True,
    )


def _pick_for_slot(
    spec: bp.SlotSpec,
    pool: list[_Cand],
    *,
    used_na_semana: set[int],
    ids_na_sessao: set[int],
    funcoes_na_sessao: set[tuple[Pattern, str]],
    prefs: frozenset[str],
    prefer_machines: bool,
    seed: int | None = None,
) -> _Cand | None:
    """O exercício certo pra uma vaga, ou None quando a base não tem nada que
    sirva. Ordem de decisão: tier, preferência da pessoa, qualidade da imagem.

    A busca é feita em três passadas cada vez mais permissivas, e é ISSO que
    implementa a regra de substituição: só relaxa uma exigência quando a
    anterior não deixou candidato nenhum.
      1ª: região exigida + função inédita no dia + exercício inédito na semana
      2ª: solta a região (mantém padrão e músculo)
      3ª: solta a variação semanal (permite repetir exercício de OUTRO dia)

    `seed`: identificador da pessoa. Só desempata entre candidatos EQUIVALENTES
    (ver `_escolher_com_variacao`) — nunca troca a ordem de decisão acima.
    """
    base = [
        c
        for c in pool
        if c.ex.primary_muscle_group == spec.muscle
        and c.taxon.pattern is spec.pattern
        and not _proibido_por_preferencia(c.nome_norm, prefs)
        and c.ex.id not in ids_na_sessao
    ]
    if not base:
        return None

    # A classe de EQUIVALÊNCIA: dois candidatos com a mesma chave cumprem a vaga
    # igualmente bem pelas regras do motor. É só entre eles que o sorteio por
    # pessoa acontece; a qualidade fica FORA da chave (ela é o desempate final) e
    # continua limitando o sorteio aos melhores do grupo.
    def equivalencia(c: _Cand) -> tuple:
        return (
            tier_rank(c.taxon.tier),
            _ordenar_por_preferencia(c.nome_norm, c.ex.equipment, prefs),
            0 if (prefer_machines and c.ex.equipment in _ESTAVEIS) else 1,
        )

    def ordenar(cands: list[_Cand]) -> list[_Cand]:
        return sorted(cands, key=lambda c: (*equivalencia(c), c.qualidade))

    def funcao_livre(c: _Cand) -> bool:
        return spec.allow_repeat_function or c.taxon.function_key not in funcoes_na_sessao

    com_regiao = [c for c in base if spec.region is None or c.taxon.region == spec.region]

    for tentativa in (
        [c for c in com_regiao if funcao_livre(c) and c.ex.id not in used_na_semana],
        [c for c in base if funcao_livre(c) and c.ex.id not in used_na_semana],
        [c for c in base if funcao_livre(c)],
    ):
        if tentativa:
            return _escolher_com_variacao(
                ordenar(tentativa), equivalencia, seed,
                spec.muscle.value, spec.pattern.value, spec.region or "-",
            )
    return None


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------
def _priorizar_ponto_fraco(
    blueprint: list[bp.SlotSpec], weak_points: list[MuscleGroup]
) -> list[bp.SlotSpec]:
    """O ponto fraco ABRE todo dia que treina ele.

    A regra mestra manda preservar desempenho nos movimentos prioritários — e se
    o músculo é prioridade da pessoa, ele é que tem que pegar a pessoa inteira,
    descansada. Duas rotas, nesta ordem:

    1. **O músculo tem composto no dia** (costas, peito, quadríceps...): promove
       esse composto pra 1ª posição. A sessão continua abrindo com movimento
       pesado, e os PAPÉIS trocam junto com as posições — sem isso a vaga
       promovida chegava em 1º ainda rotulada "composto complementar", e esse
       rótulo é texto que a pessoa lê na rotina.

    2. **O músculo não tem composto nenhum** — braço é o caso, e era o buraco:
       bíceps e tríceps não aparecem em vaga de composto em blueprint nenhum,
       então marcar braço como ponto fraco não mexia UMA VÍRGULA na ordem do
       treino. Aqui o melhor isolador dele sobe pra abertura, marcado como
       `opener` pra o validador saber que a abertura sem composto é intencional.

    O custo é real e consciente: abrir com isolador tira um pouco de desempenho
    do composto que vem depois. É exatamente o que priorizar um músculo significa,
    e só acontece quando o músculo não tem composto próprio pra promover.
    """
    if not weak_points:
        return blueprint
    if blueprint and blueprint[0].muscle in weak_points:
        return blueprint  # o dia já abre no ponto fraco (ex.: braço no dia de membros)

    compostos = [i for i, s in enumerate(blueprint) if s.pattern in _PADROES_COMPOSTOS]
    alvo = next((i for i in compostos if blueprint[i].muscle in weak_points), None)

    if alvo is not None:
        if len(compostos) < 2 or alvo == compostos[0]:
            return blueprint
        primeiro = compostos[0]
        novo = list(blueprint)
        novo.insert(primeiro, novo.pop(alvo))
        promovida, rebaixada = novo[primeiro], novo[primeiro + 1]
        novo[primeiro] = replace(promovida, role=rebaixada.role)
        novo[primeiro + 1] = replace(rebaixada, role=promovida.role)
        return novo

    # Rota 2: nenhum composto do ponto fraco neste dia. Promove o primeiro
    # isolador dele — se o dia treina o músculo. Dia que não treina o ponto fraco
    # segue como está (não vale enfiar rosca no dia de perna só pra abrir com o
    # ponto fraco: o volume dele é resolvido por VAGA, não por sequestro de dia).
    iso = next(
        (i for i, s in enumerate(blueprint) if s.muscle in weak_points and s.pattern is Pattern.ISO),
        None,
    )
    if iso is None or iso == 0:
        return blueprint
    novo = list(blueprint)
    vaga = novo.pop(iso)
    novo.insert(0, replace(vaga, role=bp.ROLE_PRIORITY_OPEN, priority=1, opener=True))
    return novo


_PADROES_COMPOSTOS = frozenset(
    {Pattern.PUSH_H, Pattern.PUSH_V, Pattern.PULL_H, Pattern.PULL_V, Pattern.KNEE, Pattern.HIP}
)


def build_plan(
    db: Session,
    method: MethodSpec,
    available_days: int | None = None,
    phase_index: int = 0,
    weak_point: MuscleGroup | None = None,
    weak_points: list[MuscleGroup] | None = None,
    session_target: int | None = None,
    time_efficient: bool = False,
    exercise_prefs: list[str] | None = None,
    seed: int | None = None,
) -> WorkoutPlan:
    """Monta a semana inteira preenchendo os blueprints de cada dia.

    weak_points: músculo(s) a priorizar (até 2). Muda a ORDEM (o composto do
    ponto fraco abre a sessão) e, via workout_builder, o VOLUME e a divisão de 4
    dias (Torso/Limbs quando o ponto fraco é músculo menor).

    session_target: nº-alvo de exercícios por sessão, vindo do tempo disponível
    (Curto 5 / Médio 6 / Longo 8). Recorta o blueprint tirando as vagas de menor
    prioridade — panturrilha/abdutor/core saem antes; composto prioritário nunca.

    time_efficient: sessão CURTA. Prioriza máquinas e cabos, que rendem mais
    estímulo por minuto e permitem a técnica avançada (myo-reps) que o coach
    prescreve nesse caso.

    seed: identificador da PESSOA (o id do usuário). Duas pessoas com respostas
    idênticas recebiam o treino idêntico, exercício por exercício. Com a semente,
    cada uma recebe a sua versão — sorteada só entre exercícios que a regra
    considera equivalentes (mesmo tier, mesmas preferências atendidas), então
    ninguém fica com treino melhor ou pior. Sem semente, a montagem é a
    determinística de sempre.

    phase_index existe só por compatibilidade de assinatura — o plano do coach
    não tem fases (a periodização dele é conduzida pelo ciclo, em cycle_state).
    """
    wp_list = list(weak_points) if weak_points else ([weak_point] if weak_point else [])
    days = resolve_days(method, available_days)
    split = coach_split_for(days, [m.value for m in wp_list])

    sets = method.sets_per_exercise or "—"
    reps = method.reps or "—"
    tempo = method.tempo
    rest = method.rest_seconds
    rir = method.rir

    prefs = frozenset(exercise_prefs or ())
    pool = _load_pool(db)

    plan = WorkoutPlan(
        method_key=method.key,
        method_name=method.name,
        author=method.author,
        days_per_week=days,
        mesocycle=method.mesocycle_weeks,
        deload_rule=method.deload_rule,
        progression_rule=method.progression_rule,
        phase_context=None,
    )

    used_na_semana: set[int] = set()
    for i, focus in enumerate(split):
        blueprint = bp.fit_to_target(bp.blueprint_for(focus), session_target)
        blueprint = _priorizar_ponto_fraco(blueprint, wp_list)

        session = PlannedSession(day_index=i, day_label=f"Dia {i + 1}", focus=focus, phase_name=None)
        ids_na_sessao: set[int] = set()
        funcoes_na_sessao: set[tuple[Pattern, str]] = set()

        for spec in blueprint:
            escolher = lambda s: _pick_for_slot(  # noqa: E731
                s,
                pool,
                used_na_semana=used_na_semana,
                ids_na_sessao=ids_na_sessao,
                funcoes_na_sessao=funcoes_na_sessao,
                prefs=prefs,
                prefer_machines=time_efficient or "maquinas" in prefs,
                seed=seed,
            )
            escolhido = escolher(spec)
            if escolhido is None:
                # Regra de substituição: nada na base preenche esta vaga (a
                # preferência da pessoa pode ter excluído todos os candidatos).
                # Tenta o equivalente que preserva a função no treino antes de
                # desistir da vaga.
                alternativa = _substituto(spec)
                if alternativa is not None:
                    escolhido = escolher(alternativa)
            if escolhido is None:
                # Nem o substituto serviu. A vaga não existe — melhor um treino
                # com uma vaga a menos do que um exercício que não cumpre o
                # papel. O validador global registra a lacuna que sobrar.
                continue
            ids_na_sessao.add(escolhido.ex.id)
            used_na_semana.add(escolhido.ex.id)
            funcoes_na_sessao.add(escolhido.taxon.function_key)
            session.slots.append(
                PlannedSlot(
                    order=len(session.slots) + 1,
                    muscle_group=escolhido.ex.primary_muscle_group.value,
                    is_compound=escolhido.taxon.is_compound,
                    exercise_id=escolhido.ex.id,
                    exercise_name=escolhido.ex.name,
                    sets=sets,
                    reps=reps,
                    tempo=tempo,
                    rest_seconds=rest,
                    rir=rir,
                    note=spec.role,
                    pattern=escolhido.taxon.pattern.value,
                    region=escolhido.taxon.region,
                    role=spec.role,
                    # Só a PRIMEIRA vaga do dia abre a sessão. Uma vaga marcada
                    # como `opener` que acabou em 2ª posição (porque a de cima
                    # sobreviveu ao recorte de tempo) é isolador comum.
                    priority_opener=spec.opener and not session.slots,
                )
            )
        plan.sessions.append(session)

    return plan


def add_accessory_slot(
    db: Session,
    plan: WorkoutPlan,
    muscle: MuscleGroup,
    *,
    prefer_machines: bool = False,
    exercise_prefs: list[str] | None = None,
    max_per_session: int = 9,
    region: str | None = None,
    seed: int | None = None,
    session: PlannedSession | None = None,
) -> PlannedSlot | None:
    """Acrescenta UMA vaga do `muscle` ao plano e devolve a vaga criada (None se
    não houver exercício novo, nenhuma sessão que treine o músculo, ou todas as
    candidatas já no teto de vagas).

    Existe porque o volume semanal de um músculo pode não caber nas vagas que
    ele tem: a saída certa é outro EXERCÍCIO, não mais séries empilhadas na
    mesma vaga (passar do teto por vaga é fadiga sem estímulo novo).

    A vaga entra na sessão que já treina esse músculo e tem menos exercícios —
    nunca num dia que não é dele. E busca uma FUNÇÃO que aquele dia ainda não
    tem: acrescentar um terceiro supino reto não é volume novo, é redundância
    (Princípio 4). Por isso o acessório é preferencialmente isolador de uma
    região descoberta.

    `region`: restringe a escolha a uma região específica. É como o reparo de
    cobertura do Princípio 6 funciona — quando a revisão global aponta que a
    semana não tem, por exemplo, 'peito clavicular', quem repara pede exatamente
    essa região em vez de "mais um exercício de peito", que poderia sair esternal
    de novo e não consertar nada.
    """
    usados = {sl.exercise_id for s in plan.sessions for sl in s.slots if sl.exercise_id is not None}

    if session is not None:
        # Quem chama já sabe QUAL dia precisa da vaga (o reforço de sessão curta,
        # que está consertando um dia específico, não procurando onde caberia
        # mais volume). O dia continua tendo que treinar o músculo: acessório em
        # dia que não é dele não é volume, é exercício solto.
        if len(session.slots) >= max_per_session:
            return None
        if not any(sl.muscle_group == muscle.value for sl in session.slots):
            return None
        sessao = session
    else:
        candidatas = [
            s
            for s in plan.sessions
            if len(s.slots) < max_per_session and any(sl.muscle_group == muscle.value for sl in s.slots)
        ]
        if not candidatas:
            return None
        sessao = min(candidatas, key=lambda s: len(s.slots))

    from collections import Counter

    # Quantas vagas da sessão cada função já ocupa. O TETO é 2, o mesmo que
    # plan_review.redundancias cobra — assim o montador e o revisor concordam por
    # construção. Sem este teto, o preenchimento de volume de um ponto fraco
    # criava um TERCEIRO exercício da mesma função (com ponto fraco em posterior
    # de coxa, a sessão saía com as 3 flexoras da base; com bíceps, 3 roscas) e o
    # revisor reprovava o treino que o próprio montador tinha acabado de montar.
    #
    # Bater no teto e não achar alternativa é melhor que furá-lo: a 3ª vaga da
    # mesma função não é volume novo, é a mesma coisa de novo. O déficit de volume
    # que sobra é reportado pelo workout_builder em vez de virar redundância.
    ocupacao = Counter((sl.pattern, sl.region) for sl in sessao.slots)
    funcoes = set(ocupacao)
    ids_sessao = {sl.exercise_id for sl in sessao.slots if sl.exercise_id is not None}
    prefs = frozenset(exercise_prefs or ())
    pool = [
        c
        for c in _load_pool(db)
        if c.ex.primary_muscle_group == muscle
        and c.ex.id not in ids_sessao
        and not _proibido_por_preferencia(c.nome_norm, prefs)
        and (region is None or c.taxon.region == region)
        and ocupacao[(c.taxon.pattern.value, c.taxon.region)] < 2
    ]
    if not pool:
        return None

    def equivalencia(c: _Cand) -> tuple:
        return (
            # 1) função que o dia ainda não tem — é o que faz a vaga ser volume
            #    novo e não repetição.
            0 if (c.taxon.pattern.value, c.taxon.region) not in funcoes else 1,
            # 2) exercício que a semana ainda não usou.
            0 if c.ex.id not in usados else 1,
            # 3) isolador antes de composto: acessório de volume não deve
            #    acrescentar fadiga sistêmica no fim do treino.
            0 if not c.taxon.is_compound else 1,
            tier_rank(c.taxon.tier),
            _ordenar_por_preferencia(c.nome_norm, c.ex.equipment, prefs),
            0 if (prefer_machines and c.ex.equipment in _ESTAVEIS) else 1,
        )

    ordenados = sorted(pool, key=lambda c: (*equivalencia(c), c.qualidade))
    escolhido = _escolher_com_variacao(
        ordenados, equivalencia, seed, "acessorio", muscle.value, region or "-", len(sessao.slots)
    )
    modelo = sessao.slots[-1]
    slot = PlannedSlot(
        order=0,  # reordenado abaixo
        muscle_group=muscle.value,
        is_compound=escolhido.taxon.is_compound,
        exercise_id=escolhido.ex.id,
        exercise_name=escolhido.ex.name,
        sets=modelo.sets,
        reps=modelo.reps,
        tempo=modelo.tempo,
        rest_seconds=modelo.rest_seconds,
        rir=modelo.rir,
        note="volume semanal",
        pattern=escolhido.taxon.pattern.value,
        region=escolhido.taxon.region,
        role="volume semanal",
    )

    # Onde inserir: um COMPOSTO nunca entra depois de um músculo menor
    # (panturrilha/abdutor/core fecham o treino). Isolador entra antes dos
    # menores; menor entra no fim.
    if escolhido.taxon.order_class >= ORDER_MINOR:
        sessao.slots.append(slot)
    else:
        primeiro_menor = next(
            (i for i, sl in enumerate(sessao.slots) if _ordem_da_vaga(sl) >= ORDER_MINOR),
            len(sessao.slots),
        )
        sessao.slots.insert(primeiro_menor, slot)
    for i, sl in enumerate(sessao.slots, start=1):
        sl.order = i
    return slot


def drop_surplus_slot(
    plan: WorkoutPlan,
    muscle: MuscleGroup,
    *,
    pode_remover=None,
    min_por_sessao: int = 0,
) -> PlannedSlot | None:
    """Tira UMA vaga do `muscle` e devolve a que saiu (None se não dá pra tirar).

    É o inverso de `add_accessory_slot`, e existe pelo mesmo motivo: uma vaga
    entrega no mínimo PER_EXERCISE_MIN séries de trabalho. Quando o alvo semanal
    do músculo é MENOR do que as vagas dele conseguem entregar, o volume não cai —
    ele estoura por baixo. Era assim que a redução dos músculos financiadores era
    silenciosamente desfeita: costas com alvo 5 e 5 vagas saía com 10 séries, o
    dobro, e o ponto fraco ficava com menos volume que quem não era prioridade.

    O que NUNCA sai:
      - a vaga que ABRE a sessão (composto prioritário ou abertura do ponto
        fraco) — é ela que define o dia;
      - a última vaga de uma REGIÃO exigida na semana (Princípio 6): tirar o
        único exercício de peito clavicular economiza série e descobre a região;
      - qualquer vaga de uma sessão que já esteja no piso de `min_por_sessao` —
        o volume da SEMANA fecha por muitos caminhos, e nenhum deles pode ser
        entregar um dia com 3 exercícios. Sem este piso, em 5 e 6 dias o mesmo
        volume se espalhava fino e saíam dias de 1 a 3 vagas;
      - o que `pode_remover` vetar — é por onde quem chama protege o equilíbrio
        empurrar/puxar e joelho/quadril da semana, que só ele sabe medir.

    Ordem de saída, do mais descartável pro menos: a vaga acrescentada por volume
    ('volume semanal'), depois a que está mais perto do FIM do treino — que é a
    que a pessoa já ia cortar por cansaço — na sessão que tem mais exercícios.
    """
    regioes_unicas = {
        regiao
        for regiao in REQUIRED_REGIONS.get(muscle, ())
        if sum(
            1
            for s in plan.sessions
            for sl in s.slots
            if sl.muscle_group == muscle.value and sl.region == regiao
        )
        <= 1
    }

    candidatas: list[tuple[tuple, PlannedSession, int]] = []
    for sessao in plan.sessions:
        if len(sessao.slots) <= min_por_sessao:
            continue
        for i, sl in enumerate(sessao.slots):
            if sl.muscle_group != muscle.value or i == 0:
                continue
            if sl.region in regioes_unicas:
                continue
            if pode_remover is not None and not pode_remover(sl):
                continue
            peso = (
                0 if sl.role == "volume semanal" else 1,  # acessório de volume sai primeiro
                -len(sessao.slots),                        # da sessão mais cheia
                -i,                                        # do fim do treino pro começo
            )
            candidatas.append((peso, sessao, i))
    if not candidatas:
        return None

    _, sessao, indice = min(candidatas, key=lambda c: c[0])
    removida = sessao.slots.pop(indice)
    for i, sl in enumerate(sessao.slots, start=1):
        sl.order = i
    return removida


def _ordem_da_vaga(slot: PlannedSlot) -> int:
    """Classe de ordem de uma vaga já montada, a partir do padrão gravado nela."""
    try:
        padrao = Pattern(slot.pattern) if slot.pattern else None
    except ValueError:
        padrao = None
    return order_class_for_pattern(padrao)


# --- O que a escolha de exercício expõe pro resto do coaching --------------
# A troca de exercício (`coaching.exercise_swap`) precisa decidir pelos MESMOS
# critérios da montagem — tier, preferências da pessoa, sorteio entre
# equivalentes. Ela chama estes nomes em vez de reimplementar a regra: montador e
# trocador discordarem seria uma porta lateral pra montar um treino que a regra
# mestra reprovaria.
ESTAVEIS = _ESTAVEIS
load_candidates = _load_pool
proibido_por_preferencia = _proibido_por_preferencia
peso_de_preferencia = _ordenar_por_preferencia
escolher_com_variacao = _escolher_com_variacao


def plan_compound_ratio(plan: WorkoutPlan) -> float:
    """Proporção composto/total que o plano pratica."""
    total = sum(len(s.slots) for s in plan.sessions)
    if total == 0:
        return 0.5
    return sum(1 for s in plan.sessions for sl in s.slots if sl.is_compound) / total


def validate_plan(method: MethodSpec, plan: WorkoutPlan) -> list[str]:
    """Violações da regra mestra. Vazia = treino aprovado.

    Delegado a `plan_review.review`, que é a "Regra de coerência global" da spec
    (as 8 perguntas). Esta função continua existindo com a assinatura antiga
    porque é o que o resto do código chama.
    """
    from app.ai.plan_review import review

    return review(plan, method=method)
