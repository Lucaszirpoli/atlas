"""Monta e SALVA o treino completo da pessoa a partir das preferências do
Coaching ('Como eu monto seu treino'). Núcleo reutilizável: o endpoint
/coaching/build-workout e a ferramenta do chat do coach chamam o mesmo código.

Determinístico (sem IA): escolhe o método que casa com experiência/objetivo/
frequência, aplica ponto fraco + tempo por sessão, e grava como as rotinas
ativas — arquivando as antigas (nunca deleta, regra 4).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.methods import coach_custom_spec
from app.ai.methods_engine import build_plan
from app.coaching import cycle_state, training_brain, volume_landmarks
from app.models.coaching_technique_cue import CoachingTechniqueCue
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
    # Dias por semana: a escolha explícita da pessoa ("Dias por semana", 2–7)
    # manda; sem ela, infere dos dias do onboarding; sem nada, 3 (seguro).
    days = training_brain.valid_training_days(profile.training_days_per_week)
    if days is None:
        days = len(profile.available_days) if profile.available_days else None
    if days is None:
        days = 3
    days = max(training_brain.TRAINING_DAYS_MIN, min(days, training_brain.TRAINING_DAYS_MAX))
    # PADRÃO: o coach monta o plano DELE (fora das 10 metodologias), adaptado ao
    # objetivo e à frequência escolhida. Determinístico e só com exercícios reais
    # da base — o motor nunca inventa exercício.
    method = coach_custom_spec(goal, exp)

    weak_values = training_brain.resolve_weak_points(profile)
    wps: list[MuscleGroup] = []
    for w in weak_values:
        try:
            wps.append(MuscleGroup(w))
        except ValueError:
            pass
    session_target = training_brain.session_exercise_target(profile.session_length)
    plan = build_plan(db, method, available_days=days, weak_points=wps, session_target=session_target)

    # Volume semanal por grupo muscular (regra: sobe/desce série por músculo
    # dentro da faixa MEV-MRV baseada em evidência, ajustada por nível — nunca
    # um número fixo igual pra todo exercício, regra 6/espec. Parte 3 item 3).
    # Conta quantas vagas da semana treinam cada músculo como principal, pega
    # o alvo semanal do músculo e distribui entre essas vagas.
    weeks_acc = cycle_state.weeks_accumulating(db, user.id, datetime.now(timezone.utc))
    slot_count_by_muscle: dict[str, int] = {}
    for s in plan.sessions:
        for sl in s.slots:
            if sl.exercise_id is None:
                continue
            slot_count_by_muscle[sl.muscle_group] = slot_count_by_muscle.get(sl.muscle_group, 0) + 1

    base_by_muscle: dict[str, int] = {}
    remainder_by_muscle: dict[str, int] = {}
    for muscle_value, n_slots in slot_count_by_muscle.items():
        try:
            muscle = MuscleGroup(muscle_value)
        except ValueError:
            base_by_muscle[muscle_value], remainder_by_muscle[muscle_value] = 3, 0
            continue
        weekly = volume_landmarks.weekly_target_sets(muscle, exp, weeks_acc)
        base_by_muscle[muscle_value] = weekly // n_slots
        remainder_by_muscle[muscle_value] = weekly % n_slots

    # Substitui o treino ativo: arquiva o que existe (não deleta) e cria o novo.
    for r in db.execute(
        select(Routine).where(Routine.user_id == user.id, Routine.is_archived.is_(False))
    ).scalars():
        r.is_archived = True
    db.flush()

    # Sessão CURTA: hipertrofia é volume-dependente, então o ÚLTIMO composto e
    # o ÚLTIMO isolado de cada dia já nascem com a série fragmentada — muscle
    # round no composto, myo-reps no isolado (mesmo critério do
    # suggest_technique) — pra render mais volume sem esticar um treino de
    # pouco tempo. Os dois porque compostos vêm sempre antes na sessão (regra
    # de ordem do motor): pegar só "o último exercício" pegaria sempre um
    # isolado e muscle round nunca apareceria. Não sobrescreve uma dica já
    # ativa nesse exercício por outro motivo (ex.: platô) nem duplica ao
    # refazer o treino.
    curto = training_brain.valid_session_length(profile.session_length) == "curto"
    technique_applied: list[str] = []

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
            # Base do volume-alvo do músculo dividido pelas vagas; o resto da
            # divisão vai pro(s) primeiro(s) exercício(s) do músculo na semana.
            sets = base_by_muscle.get(sl.muscle_group, 3)
            if remainder_by_muscle.get(sl.muscle_group, 0) > 0:
                sets += 1
                remainder_by_muscle[sl.muscle_group] -= 1
            sets = max(volume_landmarks.PER_EXERCISE_MIN, min(sets, volume_landmarks.PER_EXERCISE_MAX))
            db.add(RoutineExercise(
                routine_id=routine.id, exercise_id=sl.exercise_id, sort_order=i,
                target_sets=sets,
                target_reps_min=max(1, rmin), target_reps_max=max(rmin, rmax),
                rest_seconds=max(0, _first_int(sl.rest_seconds, 90)),
                notes=sl.note,
                set_intents=training_brain.set_intents_for(sets, sl.is_compound),
            ))
            total_ex += 1
        nomes.append(nome)

        if curto:
            last_compound = next((sl for sl in reversed(slots) if sl.is_compound), None)
            last_isolation = next((sl for sl in reversed(slots) if not sl.is_compound), None)
            for finisher in (last_compound, last_isolation):
                if finisher is None:
                    continue
                ja_ativa = db.execute(
                    select(CoachingTechniqueCue.id).where(
                        CoachingTechniqueCue.user_id == user.id,
                        CoachingTechniqueCue.exercise_id == finisher.exercise_id,
                        CoachingTechniqueCue.reverted_at.is_(None),
                    )
                ).scalar_one_or_none()
                if ja_ativa is not None:
                    continue
                tech_key, tech_label, cue_text = training_brain.suggest_technique(
                    finisher.is_compound, "intensificacao", session_length="curto"
                )
                db.add(CoachingTechniqueCue(
                    user_id=user.id, finding_key=f"session_curto:{finisher.exercise_id}",
                    exercise_id=finisher.exercise_id, exercise_name=finisher.exercise_name,
                    technique=tech_key, technique_label=tech_label, cue_text=cue_text,
                ))
                technique_applied.append(f"{tech_label} no {finisher.exercise_name}")
    db.commit()

    technique_note = None
    if technique_applied:
        technique_note = (
            "Tempo curto: já marquei fragmentação de série (pra render volume sem alongar o treino) no "
            "principal composto e no isolado final de cada dia — " + "; ".join(technique_applied) + ". Vê na "
            "prévia do treino; dá pra remover em 'O que o coach mudou'."
        )

    weak_labels = [training_brain.WEAK_POINT_LABEL[w] for w in weak_values]
    weak_label = ", ".join(weak_labels) if weak_labels else None
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
        "technique_note": technique_note,
        "periodization_label": period_label,
        "message": f"Pronto — montei {len(nomes)} treino(s) pra {days} dia(s) na semana. "
                   "Já estão nas suas rotinas, é só treinar.",
    }
