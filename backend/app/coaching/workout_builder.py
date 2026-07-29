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

from app.ai import methods_engine
from app.ai.methods import coach_custom_spec
from app.ai.methods_engine import build_plan
from app.coaching import cycle_state, training_brain, volume_landmarks
from app.models.coaching_technique_cue import CoachingTechniqueCue
from app.models.exercise import MuscleGroup
from app.models.routine import Routine, RoutineExercise
from app.models.user import User


# Teto de vagas acrescentadas numa montagem. É uma trava de segurança do laço
# (o alvo semanal no pico do mesociclo pede ~32 vagas contra as ~20 do plano
# base), não uma meta — quem para o laço de verdade é o alvo ter sido atingido.
_MAX_VAGAS_EXTRAS = 24

# Exercícios por sessão que o coach não passa, mesmo com volume sobrando. É o
# mesmo teto que build_plan já respeita; passar disso deixa de ser treino e
# vira maratona, por mais denso que a técnica avançada deixe a sessão.
_MAX_EXERCICIOS_POR_SESSAO = 9

# Técnicas avançadas por sessão. Elas são o que segura o tempo quando o volume
# manda acrescentar exercício, mas todas trabalham perto da falha — em exercício
# demais viram fadiga que não recupera, e aí o volume extra não vira estímulo.
_MAX_TECNICAS_POR_SESSAO = 3


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
    # Sessão curta: prioriza compostos multiarticulares e máquinas que pegam
    # vários músculos, pra render mais estímulo no pouco tempo.
    curto = training_brain.valid_session_length(profile.session_length) == "curto"
    plan = build_plan(
        db, method, available_days=days, weak_points=wps,
        session_target=session_target, time_efficient=curto,
    )

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

    # O volume de TODOS os músculos sai de uma vez: subir o ponto fraco obriga a
    # baixar o resto (equalização do §6.1). Calcular músculo a músculo não
    # enxerga o custo sistêmico e a semana inteira estoura junto.
    musculos: list[MuscleGroup] = []
    desconhecidos: list[str] = []
    for muscle_value in slot_count_by_muscle:
        try:
            musculos.append(MuscleGroup(muscle_value))
        except ValueError:
            desconhecidos.append(muscle_value)

    plano_semanal = volume_landmarks.weekly_plan(musculos, exp, weeks_acc, weak_points=wps)

    # --- VOLUME QUE NÃO CABE NAS VAGAS -> OUTRO EXERCÍCIO -------------------
    # Uma vaga entrega no máximo PER_EXERCISE_MAX séries de trabalho efetivas.
    # Quando o alvo semanal de um músculo não cabe nas vagas que ele tem, a
    # saída é ACRESCENTAR EXERCÍCIO, não empilhar série na mesma vaga: passar do
    # teto por vaga é fadiga sem estímulo novo. Sem isto o clamp do teto cortava
    # o excedente em silêncio e a semana saía subdosada sem ninguém saber.
    #
    # Vale pra TODO músculo, não só pro ponto fraco — equilibrar com exercício é
    # o mecanismo, e a densidade (técnica avançada, abaixo) é o que segura o
    # tempo. O músculo com maior falta é servido primeiro; empate pelo nome pra
    # a montagem continuar determinística.
    #
    # O alvo semanal SOBE ao longo do mesociclo (volume_landmarks._progress), o
    # que faz o número de exercícios subir junto — que é o que fase de
    # acumulação significa. No início do ciclo quase nada é acrescentado.
    exercicios_extras: list[str] = []
    ids_extras: set[int] = set()
    for _ in range(_MAX_VAGAS_EXTRAS):
        faltas = [
            (plano_semanal[m] - slot_count_by_muscle.get(m.value, 0) * volume_landmarks.PER_EXERCISE_MAX, m.value, m)
            for m in musculos
            if plano_semanal[m] > slot_count_by_muscle.get(m.value, 0) * volume_landmarks.PER_EXERCISE_MAX
        ]
        if not faltas:
            break
        _, _, muscle = max(faltas, key=lambda f: (f[0], f[1]))
        slot = methods_engine.add_accessory_slot(
            db, plan, muscle, prefer_machines=curto, max_per_session=_MAX_EXERCICIOS_POR_SESSAO
        )
        if slot is None:
            # Sem exercício novo desse músculo na base (ou sessões cheias): o
            # alvo dele não fecha. Tira ele da fila pra não travar o laço e
            # deixar os outros músculos sem serem servidos.
            slot_count_by_muscle[muscle.value] = slot_count_by_muscle.get(muscle.value, 0)
            plano_semanal[muscle] = slot_count_by_muscle[muscle.value] * volume_landmarks.PER_EXERCISE_MAX
            continue
        slot_count_by_muscle[muscle.value] = slot_count_by_muscle.get(muscle.value, 0) + 1
        exercicios_extras.append(slot.exercise_name)
        ids_extras.add(slot.exercise_id)

    base_by_muscle: dict[str, int] = {}
    remainder_by_muscle: dict[str, int] = {}
    for muscle_value in desconhecidos:
        base_by_muscle[muscle_value], remainder_by_muscle[muscle_value] = 3, 0
    for muscle in musculos:
        n_slots = slot_count_by_muscle[muscle.value]
        weekly = plano_semanal[muscle]
        base_by_muscle[muscle.value] = weekly // n_slots
        remainder_by_muscle[muscle.value] = weekly % n_slots

    # Substitui o treino ativo: arquiva o que existe (não deleta) e cria o novo.
    for r in db.execute(
        select(Routine).where(Routine.user_id == user.id, Routine.is_archived.is_(False))
    ).scalars():
        r.is_archived = True
    db.flush()

    # TÉCNICA AVANÇADA = DENSIDADE. Ela é o que paga o tempo dos exercícios que
    # o volume mandou acrescentar: a mesma quantidade de séries de trabalho
    # efetivas sai com descanso de 15–40s dentro da série em vez de 60–90s
    # entre séries retas. Ganham técnica:
    #
    #   - o último composto e o último isolado do dia, quando a sessão é CURTA
    #     (os dois porque composto vem sempre antes na ordem: pegar só "o
    #     último exercício" pegaria sempre um isolado e muscle round nunca
    #     apareceria);
    #   - todo exercício ACRESCENTADO pelo preenchimento de volume acima, em
    #     qualquer tamanho de sessão — ele só existe pra fechar o alvo semanal,
    #     então é exatamente onde a densidade tem que entrar.
    #
    # Com teto por sessão: técnica perto da falha em exercício demais é fadiga
    # que não recupera (o próprio texto do rest-pause diz "é pontual, não pra
    # toda sessão"). Não sobrescreve dica já ativa por outro motivo (ex.: platô)
    # nem duplica ao refazer o treino.
    technique_applied: list[str] = []
    # Todo RoutineExercise criado nesta montagem, por exercício (o mesmo
    # exercício pode aparecer em mais de um dia). O teto por técnica é aplicado
    # numa passada só, DEPOIS — ver o bloco "TETO DE SÉRIES" no fim.
    routine_exercises_by_id: dict[int, list[RoutineExercise]] = {}
    is_compound_by_id: dict[int, bool] = {}

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
            routine_exercise = RoutineExercise(
                routine_id=routine.id, exercise_id=sl.exercise_id, sort_order=i,
                target_sets=sets,
                target_reps_min=max(1, rmin), target_reps_max=max(rmin, rmax),
                rest_seconds=max(0, _first_int(sl.rest_seconds, 90)),
                notes=sl.note,
                set_intents=training_brain.set_intents_for(sets, sl.is_compound),
            )
            db.add(routine_exercise)
            routine_exercises_by_id.setdefault(sl.exercise_id, []).append(routine_exercise)
            is_compound_by_id[sl.exercise_id] = bool(sl.is_compound)
            total_ex += 1
        nomes.append(nome)

        candidatos: list = []
        if curto:
            candidatos.append(next((sl for sl in reversed(slots) if sl.is_compound), None))
            candidatos.append(next((sl for sl in reversed(slots) if not sl.is_compound), None))
        candidatos += [sl for sl in slots if sl.exercise_id in ids_extras]

        vistos: set[int] = set()
        aplicadas_na_sessao = 0
        for finisher in candidatos:
            if finisher is None or finisher.exercise_id in vistos:
                continue
            vistos.add(finisher.exercise_id)
            if aplicadas_na_sessao >= _MAX_TECNICAS_POR_SESSAO:
                break
            ja_ativa = db.execute(
                select(CoachingTechniqueCue.id).where(
                    CoachingTechniqueCue.user_id == user.id,
                    CoachingTechniqueCue.exercise_id == finisher.exercise_id,
                    CoachingTechniqueCue.reverted_at.is_(None),
                )
            ).scalar_one_or_none()
            if ja_ativa is not None:
                aplicadas_na_sessao += 1  # já tem técnica: ocupa o mesmo orçamento de fadiga
                continue
            # As MESMAS quatro entradas que a análise de platô e o "aplicar
            # técnica" manual usam (suggest_technique): ponto fraco > tempo por
            # sessão > fase do ciclo > composto/isolado. O montador fixava
            # "intensificacao" e não passava o ponto fraco, então dois caminhos
            # do mesmo coach prescreviam técnicas diferentes pro mesmo
            # exercício — e a fase de acumulação (cluster/myo-reps) nunca era
            # alcançada na montagem, apesar de existir na regra.
            # Quem pediu só série normal não ganha finisher com técnica: o
            # treino cresce por exercício e volume, como o resto do motor já faz.
            if not training_brain.advanced_allowed(profile):
                continue
            try:
                eh_ponto_fraco = MuscleGroup(finisher.muscle_group) in wps
            except ValueError:
                eh_ponto_fraco = False
            tech_key, tech_label, cue_text = training_brain.suggest_technique(
                finisher.is_compound,
                training_brain.training_period(weeks_acc),
                session_length=profile.session_length,
                is_weak_point=eh_ponto_fraco,
            )
            db.add(CoachingTechniqueCue(
                user_id=user.id, finding_key=f"densidade:{finisher.exercise_id}",
                exercise_id=finisher.exercise_id, exercise_name=finisher.exercise_name,
                technique=tech_key, technique_label=tech_label, cue_text=cue_text,
            ))
            technique_applied.append(f"{tech_label} no {finisher.exercise_name}")
            aplicadas_na_sessao += 1
    db.flush()

    # --- TETO DE SÉRIES DE TRABALHO EFETIVAS --------------------------------
    # Uma passada sobre TODAS as dicas de técnica ativas da pessoa — não só as
    # que acabaram de ser criadas. Uma técnica que já vale mais de uma série
    # (rest-pause, myo-reps e muscle round contam como 2) tem que descontar do
    # teto de 3: senão o exercício fica com 3 retas + a técnica valendo 2 = 5
    # séries de trabalho, que é o dobro do permitido.
    #
    # A passada é aqui, e não junto da criação da dica, porque a dica sobrevive
    # a remontagens (ela é por usuário+exercício e nunca é revertida ao refazer
    # o treino). Aplicar só na criação deixava justamente o caso comum de fora:
    # quem já tinha a dica de uma montagem anterior recebia rotina nova sem teto.
    for cue in db.execute(
        select(CoachingTechniqueCue).where(
            CoachingTechniqueCue.user_id == user.id,
            CoachingTechniqueCue.reverted_at.is_(None),
        )
    ).scalars():
        cap = volume_landmarks.per_exercise_max_with_technique(cue.technique)
        for routine_exercise in routine_exercises_by_id.get(cue.exercise_id, []):
            if routine_exercise.target_sets > cap:
                routine_exercise.target_sets = cap
                routine_exercise.set_intents = training_brain.set_intents_for(
                    cap, is_compound_by_id.get(cue.exercise_id, False)
                )
    db.commit()

    technique_note = None
    if technique_applied:
        technique_note = (
            "Marquei fragmentação de série (rende volume com descanso curto dentro da própria série) em "
            + "; ".join(technique_applied) + ". Vê na prévia do treino; dá pra remover em 'O que o coach mudou'."
        )

    weak_labels = [training_brain.WEAK_POINT_LABEL[w] for w in weak_values]
    weak_label = ", ".join(weak_labels) if weak_labels else None
    # A sessão cresceu por um motivo específico — dizer qual, senão a pessoa
    # abre o treino e só vê "ficou mais longo".
    extra_note = None
    if exercicios_extras:
        extra_note = (
            f"Pra fechar seu volume semanal acrescentei {len(exercicios_extras)} exercício(s): "
            + ", ".join(exercicios_extras)
            + ". É outro exercício em vez de mais séries no mesmo — passar do teto de séries por "
            "exercício acumula fadiga sem estímulo novo. O treino cresce ao longo do ciclo e alivia no deload."
        )
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
        "extra_exercises_note": extra_note,
        "periodization_label": period_label,
        "message": f"Pronto — montei {len(nomes)} treino(s) pra {days} dia(s) na semana. "
                   "Já estão nas suas rotinas, é só treinar.",
    }
