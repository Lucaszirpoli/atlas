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
from app.models.exercise import Exercise, MuscleGroup

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
    if days in method.split_by_days:
        return [normalize_search_text(x) for x in method.split_by_days[days]]
    return _DEFAULT_SPLITS.get(days, _DEFAULT_SPLITS[3])[:days] or _DEFAULT_SPLITS[3]


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
) -> list[Exercise]:
    """Escolhe `count` exercícios (determinístico) dos músculos dados, do tipo
    composto/isolado pedido, evitando repetição e respeitando proibições."""
    if count <= 0 or not muscles:
        return []
    stmt = (
        select(Exercise)
        .where(
            Exercise.primary_muscle_group.in_(muscles),
            Exercise.is_compound.is_(want_compound),
            Exercise.is_custom.is_(False),
        )
        .order_by(Exercise.id)
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
    muscle_cycle = list(muscles)
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


def build_plan(
    db: Session,
    method: MethodSpec,
    available_days: int | None = None,
    phase_index: int = 0,
) -> WorkoutPlan:
    days = resolve_days(method, available_days)
    split = _split_for(method, days)
    phase = _active_phase(method, phase_index)
    per_session = _exercises_per_session(method)

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

    used_ids: set[int] = set()
    for i, focus in enumerate(split):
        muscles = _FOCUS_MUSCLES.get(focus, [MuscleGroup.FULL_BODY])
        n_compound = round(per_session * ratio)
        n_isolation = per_session - n_compound
        session = PlannedSession(
            day_index=i,
            day_label=schedule[i] if i < len(schedule) else f"Dia {i + 1}",
            focus=focus,
            phase_name=phase.name if phase else None,
        )
        order = 1
        # Compostos primeiro (ordem correta), depois isolados.
        for ex in _pick(db, muscles, True, n_compound, used_ids, forbid_heavy_week, False):
            session.slots.append(
                PlannedSlot(order, ex.primary_muscle_group.value, True, ex.id, ex.name, sets, reps, tempo, rest, rir)
            )
            order += 1
        for ex in _pick(db, muscles, False, n_isolation, used_ids, False, prefer_machines):
            session.slots.append(
                PlannedSlot(order, ex.primary_muscle_group.value, False, ex.id, ex.name, sets, reps, tempo, rest, rir)
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
