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

from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import session_blueprints as bp
from app.ai.exercise_taxonomy import (
    ORDER_MINOR,
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
) -> _Cand | None:
    """O exercício certo pra uma vaga, ou None quando a base não tem nada que
    sirva. Ordem de decisão: tier, preferência da pessoa, qualidade da imagem.

    A busca é feita em três passadas cada vez mais permissivas, e é ISSO que
    implementa a regra de substituição: só relaxa uma exigência quando a
    anterior não deixou candidato nenhum.
      1ª: região exigida + função inédita no dia + exercício inédito na semana
      2ª: solta a região (mantém padrão e músculo)
      3ª: solta a variação semanal (permite repetir exercício de OUTRO dia)
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

    def ordenar(cands: list[_Cand]) -> list[_Cand]:
        return sorted(
            cands,
            key=lambda c: (
                tier_rank(c.taxon.tier),
                _ordenar_por_preferencia(c.nome_norm, c.ex.equipment, prefs),
                0 if (prefer_machines and c.ex.equipment in _ESTAVEIS) else 1,
                c.qualidade,
            ),
        )

    def funcao_livre(c: _Cand) -> bool:
        return spec.allow_repeat_function or c.taxon.function_key not in funcoes_na_sessao

    com_regiao = [c for c in base if spec.region is None or c.taxon.region == spec.region]

    for tentativa in (
        [c for c in com_regiao if funcao_livre(c) and c.ex.id not in used_na_semana],
        [c for c in base if funcao_livre(c) and c.ex.id not in used_na_semana],
        [c for c in base if funcao_livre(c)],
    ):
        if tentativa:
            return ordenar(tentativa)[0]
    return None


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------
def _priorizar_ponto_fraco(
    blueprint: list[bp.SlotSpec], weak_points: list[MuscleGroup]
) -> list[bp.SlotSpec]:
    """Ponto fraco primeiro, DENTRO do bloco de compostos.

    A regra mestra manda preservar desempenho nos movimentos prioritários — e se
    o músculo é prioridade da pessoa, ele é que tem que pegar a pessoa inteira.
    Mas não vale jogar um isolador de bíceps pra abrir o treino: a troca só
    acontece entre vagas de composto (ordem 1), então a sessão continua abrindo
    com um movimento pesado.
    """
    if not weak_points:
        return blueprint
    compostos = [i for i, s in enumerate(blueprint) if s.pattern in _PADROES_COMPOSTOS]
    if len(compostos) < 2:
        return blueprint
    alvo = next(
        (i for i in compostos if blueprint[i].muscle in weak_points),
        None,
    )
    if alvo is None or alvo == compostos[0]:
        return blueprint
    novo = list(blueprint)
    vaga = novo.pop(alvo)
    novo.insert(compostos[0], vaga)
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

    candidatas = [
        s
        for s in plan.sessions
        if len(s.slots) < max_per_session and any(sl.muscle_group == muscle.value for sl in s.slots)
    ]
    if not candidatas:
        return None
    sessao = min(candidatas, key=lambda s: len(s.slots))

    funcoes = {(sl.pattern, sl.region) for sl in sessao.slots}
    ids_sessao = {sl.exercise_id for sl in sessao.slots if sl.exercise_id is not None}
    prefs = frozenset(exercise_prefs or ())
    pool = [
        c
        for c in _load_pool(db)
        if c.ex.primary_muscle_group == muscle
        and c.ex.id not in ids_sessao
        and not _proibido_por_preferencia(c.nome_norm, prefs)
        and (region is None or c.taxon.region == region)
    ]
    if not pool:
        return None

    def chave(c: _Cand) -> tuple:
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
            c.qualidade,
        )

    escolhido = min(pool, key=chave)
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


def _ordem_da_vaga(slot: PlannedSlot) -> int:
    """Classe de ordem de uma vaga já montada, a partir do padrão gravado nela."""
    try:
        padrao = Pattern(slot.pattern) if slot.pattern else None
    except ValueError:
        padrao = None
    return order_class_for_pattern(padrao)


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
