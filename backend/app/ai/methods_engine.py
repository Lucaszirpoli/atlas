"""Motor DETERMINÍSTICO de montagem de treino por metodologia.

Recebe uma MethodSpec (app/ai/methods.py) + o perfil do usuário e constrói o
esqueleto do treino já respeitando as regras do método: frequência/agenda,
split, número de exercícios, PROPORÇÃO composto/isolado dentro de cada sessão,
séries/reps/cadência/descanso da fase ativa, ordem (compostos antes) e
proibições de segurança. Uma validação (`validate_plan`) rejeita qualquer
plano que viole as regras — é o que garante a fidelidade que a IA sozinha não
dava. A camada de IA (methods_ai) depois pode trocar a SELEÇÃO de exercícios
de cada vaga, mas nunca as regras.

A seleção aqui é determinística (mesma entrada → mesmo plano), então o produto
já é válido mesmo sem a IA; a IA só personaliza dentro dos trilhos.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.methods import MethodSpec, Phase
from app.core.text import normalize_search_text
from app.models.exercise import (
    EXTENDED_STRENGTH_CATEGORIES,
    STRENGTH_CATEGORIES,
    Exercise,
    MuscleGroup,
    quality_order,
)

# Grupos musculares treinados por cada rótulo de "foco" usado nos splits.
_FOCUS_MUSCLES: dict[str, list[MuscleGroup]] = {
    "peito": [MuscleGroup.CHEST],
    "costas": [MuscleGroup.BACK],
    "pernas": [MuscleGroup.QUADS, MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.CALVES],
    "ombros": [MuscleGroup.SHOULDERS],
    "bracos": [MuscleGroup.BICEPS, MuscleGroup.TRICEPS],
    "peito/costas": [MuscleGroup.CHEST, MuscleGroup.BACK],
    "ombros/bracos": [MuscleGroup.SHOULDERS, MuscleGroup.BICEPS, MuscleGroup.TRICEPS],
    "push": [MuscleGroup.CHEST, MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS],
    "pull": [MuscleGroup.BACK, MuscleGroup.BICEPS],
    "superior": [MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.SHOULDERS, MuscleGroup.BICEPS, MuscleGroup.TRICEPS],
    "inferior": [MuscleGroup.QUADS, MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.CALVES],
    "full body": [MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.QUADS, MuscleGroup.SHOULDERS, MuscleGroup.BICEPS],
    "full body a": [MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.QUADS, MuscleGroup.SHOULDERS],
    "full body b": [MuscleGroup.BACK, MuscleGroup.HAMSTRINGS, MuscleGroup.SHOULDERS, MuscleGroup.BICEPS, MuscleGroup.TRICEPS],
    "a": [MuscleGroup.CHEST, MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS, MuscleGroup.QUADS],
    "b": [MuscleGroup.BACK, MuscleGroup.BICEPS, MuscleGroup.HAMSTRINGS, MuscleGroup.CALVES],
    # --- Métodos de FORÇA -------------------------------------------------
    # 5/3/1 e Juggernaut nomeiam o dia pelo levantamento principal; Westside
    # usa ME/DE (esforço máximo / dinâmico) por metade do corpo. Sem estes
    # mapeamentos eles caíam em "full body" e o motor sorteava exercício
    # genérico (burpee, kettlebell swing) num treino de powerlifting.
    "agachamento": [MuscleGroup.QUADS, MuscleGroup.GLUTES, MuscleGroup.HAMSTRINGS],
    "supino": [MuscleGroup.CHEST, MuscleGroup.TRICEPS, MuscleGroup.SHOULDERS],
    # BICEPS no dia de terra: é o dia de puxada, e tanto o 5/3/1 (assistência
    # "Boring But Big"/Triumvirate) quanto o Juggernaut prescrevem rosca como
    # acessório. Sem isto, os dois métodos inteiros saíam sem um exercício de
    # bíceps em nenhum dos 4 dias.
    "terra": [MuscleGroup.BACK, MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.BICEPS],
    "desenvolvimento": [MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS, MuscleGroup.TRAPS],
    "me inferior": [MuscleGroup.QUADS, MuscleGroup.GLUTES, MuscleGroup.HAMSTRINGS],
    "de inferior": [MuscleGroup.QUADS, MuscleGroup.GLUTES, MuscleGroup.HAMSTRINGS],
    # BICEPS entra aqui de propósito: sem ele, o Westside inteiro (4 dias)
    # saía sem UM exercício de bíceps sequer — e "acessório pra ponto fraco"
    # é justamente o que o método prega. Mesmo motivo pra TRAPS no ME/DE.
    "me superior": [
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.TRICEPS,
        MuscleGroup.BICEPS,
    ],
    "de superior": [
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.TRICEPS,
        MuscleGroup.BICEPS,
    ],
}

# Levantamento PRINCIPAL de cada dia, quando o método define o dia por ele
# (5/3/1, Juggernaut) ou pede um esforço máximo naquele padrão (Westside ME).
# O motor força este exercício como o 1º da sessão — é o que faz o método ser
# ele mesmo: um "dia de agachamento" tem que começar agachando.
_FOCUS_PRIMARY_LIFT: dict[str, str] = {
    "agachamento": "agachamento livre com barra",
    "supino": "supino reto com barra",
    "terra": "levantamento terra",
    "desenvolvimento": "desenvolvimento militar com barra",
    "me inferior": "agachamento livre com barra",
    "me superior": "supino reto com barra",
    "de inferior": "agachamento livre com barra",
    "de superior": "supino reto com barra",
}

# Splits padrão por nº de dias, quando o método não fixa um.
_DEFAULT_SPLITS: dict[int, list[str]] = {
    2: ["full body a", "full body b"],
    3: ["push", "pull", "pernas"],
    4: ["superior", "inferior", "superior", "inferior"],
    5: ["peito", "costas", "pernas", "ombros", "bracos"],
    6: ["push", "pull", "pernas", "push", "pull", "pernas"],
}

# Lifts compostos pesados proibidos em certas fases (Y3T infernal, FST-7
# finalizador). Casados por palavra-chave no nome normalizado.
_HEAVY_COMPOUND_KEYWORDS = ("agachamento", "supino", "terra", "levantamento terra")


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
    """Casa a disponibilidade do usuário com os dias suportados pelo método —
    escolhe o maior nº suportado que não passa da disponibilidade; se a pessoa
    tem menos dias que o mínimo do método, usa o mínimo (com aviso)."""
    supported = sorted(method.days_per_week) or [3]
    if available_days is None:
        return supported[0]
    feasible = [d for d in supported if d <= available_days]
    return feasible[-1] if feasible else supported[0]


def _split_for(method: MethodSpec, days: int) -> list[str]:
    """Foco de cada dia da semana. Vários métodos descrevem o split como um
    CICLO curto que se repete (ex: DC Training = A/B alternando, então 4 dias =
    A,B,A,B). Antes devolvíamos só as entradas do ciclo (2), e o app criava 2
    rotinas em vez de 4 — o resto dos dias sumia. Agora o ciclo é repetido até
    cobrir todos os dias pedidos."""
    if days in method.split_by_days:
        base = [normalize_search_text(x) for x in method.split_by_days[days]]
    else:
        base = list(_DEFAULT_SPLITS.get(days, _DEFAULT_SPLITS[3]))
    if not base:
        base = list(_DEFAULT_SPLITS[3])
    return [base[i % len(base)] for i in range(days)]


def _active_phase(method: MethodSpec, phase_index: int) -> Phase | None:
    if method.phases and 0 <= phase_index < len(method.phases):
        return method.phases[phase_index]
    return None


def _exercises_per_session(method: MethodSpec) -> int:
    # Heurística por família; fiel ao "poucos exercícios" dos métodos HIT.
    if method.key in ("mentzer_hit", "dc_training"):
        return 4
    if method.key in ("wendler_531", "juggernaut", "westside"):
        return 5  # 1 principal + acessórios
    if method.key == "fst7":
        return 4  # composto pesado + secundário + isolamento + finalizador
    return 6


def _pick(
    db: Session,
    muscles: list[MuscleGroup],
    want_compound: bool,
    count: int,
    used_ids: set[int],
    forbid_heavy: bool,
    equipment_pref_machines: bool,
    covered: frozenset[MuscleGroup] = frozenset(),
) -> list[Exercise]:
    """Escolhe `count` exercícios (determinístico) dos músculos dados, do tipo
    composto/isolado pedido, evitando repetição e respeitando proibições."""
    if count <= 0 or not muscles:
        return []
    # Prefere exercícios COM foto de demonstração (video_url != NULL) — assim
    # o treino gerado mostra a imagem de cada exercício. Empate: por id.
    stmt = (
        select(Exercise)
        .where(
            Exercise.primary_muscle_group.in_(muscles),
            Exercise.is_compound.is_(want_compound),
            Exercise.is_custom.is_(False),
            Exercise.is_hidden.is_(False),
            # Só musculação. Sem isto, a base importada devolvia alongamento
            # ("All Fours Quad Stretch"), mobilidade ("Ankle Circles") e
            # levantamento olímpico como se fossem exercício de rotina — foi
            # o que gerou o "treino de perna" com três alongamentos dentro.
            Exercise.category.in_(STRENGTH_CATEGORIES),
        )
        .order_by(*quality_order())
    )
    candidates = list(db.execute(stmt).scalars())
    out: list[Exercise] = []
    # Distribui entre os músculos do foco em rodízio, pra não empilhar tudo num só.
    by_muscle: dict[MuscleGroup, list[Exercise]] = {m: [] for m in muscles}
    for ex in candidates:
        if ex.id in used_ids:
            continue
        if forbid_heavy and any(k in normalize_search_text(ex.name) for k in _HEAVY_COMPOUND_KEYWORDS):
            continue
        if ex.primary_muscle_group in by_muscle:
            by_muscle[ex.primary_muscle_group].append(ex)
    # preferência por máquinas quando o método pede (FST-7 finalizador, Kuba)
    if equipment_pref_machines:
        from app.models.exercise import Equipment

        for m in by_muscle:
            by_muscle[m].sort(key=lambda e: 0 if e.equipment in (Equipment.MACHINE, Equipment.CABLE) else 1)
    idx = 0
    # Músculo que AINDA não tem exercício nesta sessão vem primeiro. Girar a
    # lista por contagem (o que eu fazia antes) não bastava: bíceps não tem
    # exercício COMPOSTO nenhum, então ele era pulado na passada dos compostos
    # e o deslocamento da passada dos isolados caía no lugar errado — o dia de
    # "ombros/braços" do Mentzer e o A/B do DC saíam sem UMA rosca sequer.
    # sorted é estável, então quem está descoberto mantém a ordem original.
    muscle_cycle = sorted(muscles, key=lambda m: m in covered)
    while len(out) < count and any(by_muscle[m] for m in muscle_cycle):
        m = muscle_cycle[idx % len(muscle_cycle)]
        if by_muscle[m]:
            ex = by_muscle[m].pop(0)
            out.append(ex)
            used_ids.add(ex.id)
        idx += 1
        if idx > 500:
            break
    return out


def _so_existe_isolado(db: Session, muscles: list[MuscleGroup]) -> bool:
    """True se algum músculo do foco não tem NENHUM exercício composto — caso
    do bíceps. Serve pra garantir uma vaga de isolado quando o método pediria
    só composto, senão esse músculo nunca é treinado."""
    for m in muscles:
        tem = db.execute(
            select(Exercise.id)
            .where(
                Exercise.primary_muscle_group == m,
                Exercise.is_compound.is_(True),
                Exercise.is_custom.is_(False),
                Exercise.is_hidden.is_(False),
                Exercise.category.in_(STRENGTH_CATEGORIES),
            )
            .limit(1)
        ).first()
        if tem is None:
            return True
    return False


def _find_exercise(db: Session, name_query: str) -> Exercise | None:
    """Acha um exercício específico pelo nome (levantamento principal do dia).
    Prefere o de menor id — a base curada (nomes limpos) vem antes da importada.

    Aceita o pool ampliado (olímpico/strongman/pliometria) de propósito: alguns
    métodos pedem esses levantamentos pelo nome (5/3/1 usa terra e
    desenvolvimento; Westside usa trenó). O que nunca entra é alongamento/cardio.
    """
    return db.execute(
        select(Exercise)
        .where(
            Exercise.name.ilike(f"%{name_query}%"),
            Exercise.is_custom.is_(False),
            Exercise.is_hidden.is_(False),
            Exercise.category.in_(EXTENDED_STRENGTH_CATEGORIES),
        )
        .order_by(*quality_order())
    ).scalars().first()


def build_plan(
    db: Session,
    method: MethodSpec,
    available_days: int | None = None,
    phase_index: int = 0,
    weak_point: MuscleGroup | None = None,
    session_target: int | None = None,
) -> WorkoutPlan:
    """weak_point: músculo a priorizar nos acessórios. Só faz sentido nos
    métodos desenhados pra isso (Westside: "3-5 acessórios de 10-20 reps para
    pontos fracos"; Mountain Dog). Quando informado, o músculo entra no início
    do rodízio de TODO dia que o treine — é o que faz a escolha mudar o treino
    de verdade em vez de virar enfeite na tela.

    session_target: nº-alvo de exercícios por sessão (vem do tempo disponível da
    pessoa — Curto/Médio/Longo). Sobrepõe o padrão do método, mas dentro de um
    limite seguro (3–9) pra não descaracterizar métodos minimalistas nem estourar
    a proporção composto/isolado que a validação cobra."""
    days = resolve_days(method, available_days)
    split = _split_for(method, days)
    phase = _active_phase(method, phase_index)
    per_session = _exercises_per_session(method)
    if session_target is not None:
        per_session = max(3, min(int(session_target), 9))

    # Proporção composto/isolado (default 0.5 quando o método não fixa).
    ratio = method.compound_ratio if method.compound_ratio is not None else 0.5

    # Parâmetros da fase ativa (ou base do método).
    sets = (phase.sets if phase else None) or method.sets_per_exercise or "—"
    reps = (phase.reps if phase else None) or method.reps or "—"
    tempo = (phase.tempo if phase else None) or method.tempo
    rest = (phase.rest_seconds if phase else None) or method.rest_seconds
    rir = (phase.rir if phase else None) or method.rir

    # Proibição de composto pesado: Y3T semana infernal (fase index 2) e o
    # finalizador do FST-7 (tratado no builder de fase por sessão).
    forbid_heavy_week = method.key == "y3t" and phase_index == 2

    schedule = method.schedule_suggestions.get(days, [])
    prefer_machines = method.key in ("kuba", "fst7")

    plan = WorkoutPlan(
        method_key=method.key,
        method_name=method.name,
        author=method.author,
        days_per_week=days,
        mesocycle=method.mesocycle_weeks,
        deload_rule=method.deload_rule,
        progression_rule=method.progression_rule,
        phase_context=phase.name if phase else None,
    )
    if available_days is not None and days > available_days:
        plan.notes.append(
            f"Você informou {available_days} dia(s), mas {method.name} pede no mínimo {days}. "
            "Ajuste a agenda ou considere um método de menor frequência."
        )

    # Métodos HIT prescrevem UMA série de trabalho de propósito — sem explicar,
    # o treino parece incompleto/quebrado ("só 1 série?"). Deixa explícito.
    if str(sets).strip().startswith("1"):
        plan.notes.append(
            f"1 série de trabalho por exercício é intencional no {method.name}: a série é levada ao "
            "limite, então volume extra atrapalharia a recuperação. Faça séries de aquecimento antes, "
            "sem falhar — elas não contam como série de trabalho."
        )

    used_ids: set[int] = set()
    # Um foco que se repete na semana (ex: A,B,A,B do DC) é o MESMO treino —
    # então a seleção de exercícios é feita UMA vez por foco e reaproveitada.
    # Sem isso, o used_ids daria exercícios diferentes no segundo dia "A".
    picked_by_focus: dict[str, list[tuple[Exercise, bool]]] = {}

    for i, focus in enumerate(split):
        if focus not in picked_by_focus:
            muscles = _FOCUS_MUSCLES.get(focus, [MuscleGroup.FULL_BODY])
            # Ponto fraco primeiro no rodízio, nos dias que já treinam esse
            # músculo. Não o enfia num dia que não é dele (perna no dia de
            # supino não vira "prioridade", vira treino incoerente).
            if weak_point is not None and weak_point in muscles:
                muscles = [weak_point] + [m for m in muscles if m != weak_point]
            n_compound = round(per_session * ratio)
            n_isolation = per_session - n_compound

            # Bíceps não existe como exercício COMPOSTO. Num método de
            # proporção quase toda composta (Mentzer HIT: 0.9 -> 4 compostos e
            # 0 isolados em 4 vagas), ele fica matematicamente inalcançável e o
            # dia de "ombros/braços" sai sem uma rosca sequer — sendo que é
            # justamente o dia mais isolado do Heavy Duty original. Reservar
            # UMA vaga cabe na tolerância de 1 da validate_plan, então o método
            # continua fiel.
            if n_isolation == 0 and n_compound > 1 and _so_existe_isolado(db, muscles):
                n_compound -= 1
                n_isolation = 1

            # Levantamento principal do dia primeiro (5/3/1: dia de agachamento
            # começa agachando). Só quando o método define o dia pelo lift e a
            # fase não proíbe composto pesado.
            compounds: list[Exercise] = []
            primary_query = _FOCUS_PRIMARY_LIFT.get(focus)
            if primary_query and not forbid_heavy_week and n_compound > 0:
                primary = _find_exercise(db, primary_query)
                if primary is not None and primary.id not in used_ids:
                    compounds.append(primary)
                    used_ids.add(primary.id)

            # Cada passada mira o que ainda está descoberto, em vez de recomeçar
            # a lista do zero. Sem isso os músculos do fim morriam de fome: em
            # "me superior" ([peito, costas, ombro, tríceps, bíceps]) os
            # compostos pegavam peito/costas/ombro e os isolados voltavam pro
            # peito — o dia saía com três peitos e zero braço.
            compounds += _pick(
                db,
                muscles,
                True,
                n_compound - len(compounds),
                used_ids,
                forbid_heavy_week,
                False,
                covered=frozenset(e.primary_muscle_group for e in compounds),
            )
            isolations = _pick(
                db,
                muscles,
                False,
                n_isolation,
                used_ids,
                False,
                prefer_machines,
                covered=frozenset(e.primary_muscle_group for e in compounds),
            )
            picked_by_focus[focus] = [(ex, True) for ex in compounds] + [(ex, False) for ex in isolations]

        session = PlannedSession(
            day_index=i,
            day_label=schedule[i] if i < len(schedule) else f"Dia {i + 1}",
            focus=focus,
            phase_name=phase.name if phase else None,
        )
        order = 1
        for ex, is_compound in picked_by_focus[focus]:
            session.slots.append(
                PlannedSlot(
                    order, ex.primary_muscle_group.value, is_compound, ex.id, ex.name, sets, reps, tempo, rest, rir
                )
            )
            order += 1
        plan.sessions.append(session)

    return plan


def validate_plan(method: MethodSpec, plan: WorkoutPlan) -> list[str]:
    """Devolve a lista de violações das regras do método. Vazia = plano fiel."""
    problems: list[str] = []

    # 1) Proporção composto/isolado dentro de CADA sessão (tolerância de 1 vaga).
    if method.compound_ratio is not None:
        for s in plan.sessions:
            total = len(s.slots)
            if total == 0:
                continue
            comp = sum(1 for sl in s.slots if sl.is_compound)
            expected = round(total * method.compound_ratio)
            if abs(comp - expected) > 1:
                problems.append(
                    f"Sessão '{s.focus}': {comp}/{total} compostos, esperado ~{expected} "
                    f"(proporção {int(method.compound_ratio * 100)}% do método)."
                )

    # 2) Frequência: nº de sessões bate com os dias suportados.
    if plan.days_per_week not in method.days_per_week and method.days_per_week:
        problems.append(
            f"{plan.days_per_week} dias não é uma frequência suportada por {method.name} "
            f"({', '.join(map(str, method.days_per_week))})."
        )

    # 3) Ordem: nenhum isolado antes de um composto na mesma sessão.
    for s in plan.sessions:
        seen_iso = False
        for sl in s.slots:
            if not sl.is_compound:
                seen_iso = True
            elif seen_iso:
                problems.append(f"Sessão '{s.focus}': composto '{sl.exercise_name}' veio depois de um isolado (ordem incorreta).")
                break

    # 4) Proibições: Y3T semana infernal sem composto pesado.
    if method.key == "y3t" and plan.phase_context and "infernal" in plan.phase_context.lower():
        for s in plan.sessions:
            for sl in s.slots:
                if any(k in normalize_search_text(sl.exercise_name) for k in _HEAVY_COMPOUND_KEYWORDS):
                    problems.append(f"Semana infernal (Y3T) não pode ter composto pesado: '{sl.exercise_name}'.")

    return problems
