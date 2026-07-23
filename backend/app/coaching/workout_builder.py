"""Monta e SALVA o treino completo da pessoa a partir das preferências do
Coaching ('Como eu monto seu treino'). Núcleo reutilizável: o endpoint
/coaching/build-workout e a ferramenta do chat do coach chamam o mesmo código.

Determinístico (sem IA): escolhe o método que casa com experiência/objetivo/
frequência, aplica ponto fraco + tempo por sessão, e grava como as rotinas
ativas — arquivando as antigas (nunca deleta, regra 4).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.methods import get_method, recommend_method_for_profile
from app.ai.methods_engine import build_plan
from app.coaching import training_brain
from app.models.exercise import MuscleGroup
from app.models.routine import Routine, RoutineExercise
from app.models.user import User


def _first_int(s, default: int) -> int:
    m = re.search(r"\d+", str(s or ""))
    return int(m.group()) if m else default


def _parse_reps(s) -> tuple[int, int]:
    """Faixa de reps a partir do texto do método ('8-12', '6', '15-30+')."""
    txt = str(s or "")
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)", txt)
    if m:
        return int(m.group(1)), int(m.group(2))
    one = re.search(r"\d+", txt)
    if one:
        n = int(one.group())
        return n, n
    return 8, 12


def build_and_save(db: Session, user: User) -> dict:
    """Monta o treino pelas prefs e substitui as rotinas ativas. Devolve um
    resumo (método, dias, rotinas, ponto fraco, cardio, periodização)."""
    profile = getattr(user, "profile", None)
    if profile is None:
        raise ValueError("Complete seu perfil primeiro.")

    exp = profile.experience_level.value if profile.experience_level else None
    goal = profile.goal.value if profile.goal else None
    days = len(profile.available_days) if profile.available_days else None
    method = get_method(recommend_method_for_profile(exp, goal, days))
    if method is None:
        raise ValueError("Não achei um método pra montar agora.")

    weak = training_brain.valid_weak_point(profile.weak_point)
    wp: MuscleGroup | None = None
    if weak:
        try:
            wp = MuscleGroup(weak)
        except ValueError:
            wp = None
    session_target = training_brain.session_exercise_target(profile.session_length)
    plan = build_plan(db, method, available_days=days, weak_point=wp, session_target=session_target)

    # Substitui o treino ativo: arquiva o que existe (não deleta) e cria o novo.
    for r in db.execute(
        select(Routine).where(Routine.user_id == user.id, Routine.is_archived.is_(False))
    ).scalars():
        r.is_archived = True
    db.flush()

    nomes: list[str] = []
    total_ex = 0
    for s in plan.sessions:
        slots = [sl for sl in s.slots if sl.exercise_id is not None]
        if not slots:
            continue
        nome = f"{method.name} — {s.day_label} · {s.focus}"[:100]
        routine = Routine(user_id=user.id, name=nome)
        db.add(routine)
        db.flush()
        for i, sl in enumerate(slots):
            rmin, rmax = _parse_reps(sl.reps)
            db.add(RoutineExercise(
                routine_id=routine.id, exercise_id=sl.exercise_id, sort_order=i,
                target_sets=max(1, min(_first_int(sl.sets, 3), 8)),
                target_reps_min=max(1, rmin), target_reps_max=max(rmin, rmax),
                rest_seconds=max(0, _first_int(sl.rest_seconds, 90)),
                notes=sl.note,
            ))
            total_ex += 1
        nomes.append(nome)
    db.commit()

    weak_label = training_brain.WEAK_POINT_LABEL.get(weak) if weak else None
    if profile.wants_cardio:
        cardio_note = ("Como você quer cardio, inclua 2× de 20–30 min na semana (esteira, bike ou elíptico), "
                       "de preferência longe dos dias pesados de perna.")
    else:
        cardio_note = training_brain.cardio_warning(goal, profile.wants_cardio)
    period_label = training_brain.PERIODIZATION_LABEL.get(
        training_brain.valid_periodization(profile.periodization), "Automática"
    )
    return {
        "method_name": method.name,
        "author": method.author,
        "days": len(nomes),
        "routines": nomes,
        "total_exercises": total_ex,
        "weak_point_label": weak_label,
        "session_range": training_brain.session_range_text(profile.session_length),
        "cardio_note": cardio_note,
        "periodization_label": period_label,
        "message": f"Pronto — montei {len(nomes)} treino(s) no método {method.name}. "
                   "Já estão nas suas rotinas, é só treinar.",
    }
