""""Pronto pra subir a carga" (Cap. XVI Parte D do manual) tem que comparar
contra o que foi PRESCRITO pra aquele exercício específico, nunca um número
fixo pra qualquer exercício.

Até 2026-07-31 o sinal usava um teto de 12 repetições (18 pra peso corporal) e
"folga = RIR ≥ 1", iguais pra TODO exercício. Isso quebrou de verdade quando a
faixa de reps passou a variar por exercício (Cap. XI, mesmo commit que criou
`coaching/prescription.py`):

  - um agachamento livre prescrito em 5-9 quase nunca bateria 12 reps — o sinal
    nunca disparava, mesmo com a pessoa estourando a faixa dela havia semanas;
  - uma elevação lateral prescrita em 10-15 disparava aos 12 — três repetições
    antes do topo real da faixa dela, mandando subir peso cedo demais.

Esta suíte não existia (dava pra quebrar a detecção de progressão inteira e a
suíte seguir verde — foi exatamente o que aconteceu). Ela testa
`metrics.compute_metrics` de ponta a ponta contra sessões de treino de verdade.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.coaching import metrics
from app.models.exercise import Exercise
from app.models.user import Plan, User
from app.models.user_profile import (
    ActivityLevel, BiologicalSex, ExperienceLevel, Goal, TrainingLocation, UserProfile,
)
from app.models.workout_session import SetType, WorkoutSession, WorkoutSetLog

AGORA = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def db():
    from app.core.db import SessionLocal

    s = SessionLocal()
    if s.execute(select(Exercise.id).where(Exercise.is_hidden.is_(False)).limit(1)).first() is None:
        s.close()
        pytest.skip("biblioteca de exercícios não semeada neste banco")
    yield s
    s.close()


def _exercicio(db, nome: str) -> Exercise:
    # `.name == nome` pode bater mais de uma linha (ex.: uma linha antiga
    # escondida do free-exercise-db convivendo com a curada) — a visível é a
    # que interessa, e só ela.
    ex = db.execute(
        select(Exercise).where(Exercise.name == nome, Exercise.is_hidden.is_(False)).limit(1)
    ).scalar_one_or_none()
    if ex is None:
        pytest.skip(f"exercício '{nome}' não está semeado neste banco")
    return ex


@pytest.fixture
def usuario(db):
    email = "__tmp_prog__@teste.local"

    def limpar():
        u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if u is None:
            return
        sids = [s for (s,) in db.execute(
            select(WorkoutSession.id).where(WorkoutSession.user_id == u.id)
        ).all()]
        if sids:
            db.execute(delete(WorkoutSetLog).where(WorkoutSetLog.session_id.in_(sids)))
            db.execute(delete(WorkoutSession).where(WorkoutSession.id.in_(sids)))
        db.execute(delete(UserProfile).where(UserProfile.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
        db.commit()

    limpar()
    u = User(email=email, handle="__tmp_pr__", display_name="T", password_hash="x", plan=Plan.PRO)
    db.add(u)
    db.flush()
    db.add(UserProfile(
        user_id=u.id, age=30, height_cm=180,
        biological_sex=BiologicalSex.MALE, activity_level=ActivityLevel.MODERATE,
        training_location=TrainingLocation.ACADEMIA_COMPLETA,
        experience_level=ExperienceLevel.INTERMEDIARIO, goal=Goal.HIPERTROFIA,
    ))
    db.commit()
    db.refresh(u)
    try:
        yield u
    finally:
        limpar()


def _sessao(db, user_id: int, dias_atras: int) -> WorkoutSession:
    s = WorkoutSession(
        user_id=user_id,
        started_at=AGORA - timedelta(days=dias_atras),
        completed_at=AGORA - timedelta(days=dias_atras) + timedelta(minutes=45),
    )
    db.add(s)
    db.flush()
    return s


def _serie(db, session_id: int, exercise_id: int, *, peso: float, reps: int, rir: int | None):
    db.add(WorkoutSetLog(
        session_id=session_id, exercise_id=exercise_id, set_number=1,
        weight_kg=peso, reps=reps, rir=rir, set_type=SetType.STRAIGHT,
    ))


def _progression_names(db, user_id: int) -> set[str]:
    m = metrics.compute_metrics(db, user_id, window_days=28, now=AGORA)
    return {p["name"] for p in m.training.progression_lifts}


# --- Faixa BAIXA: o sinal tem que disparar no topo REAL, não em 12 ----------
def test_faixa_baixa_dispara_no_topo_dela_nao_em_doze(db, usuario):
    """Terra romeno é prescrito 5-9 reps. Com o teto fixo antigo (12), este
    sinal NUNCA disparava pra este exercício — a pessoa podia estourar a faixa
    dela há semanas e o coach nunca notava."""
    ex = _exercicio(db, "Levantamento terra romeno")

    s1 = _sessao(db, usuario.id, dias_atras=14)
    _serie(db, s1.id, ex.id, peso=60, reps=8, rir=None)
    s2 = _sessao(db, usuario.id, dias_atras=1)
    _serie(db, s2.id, ex.id, peso=60, reps=9, rir=None)  # bate o topo da FAIXA DELA (9)
    db.commit()

    assert "Levantamento terra romeno" in _progression_names(db, usuario.id), (
        "não disparou no topo real da faixa prescrita (5-9)"
    )


def test_faixa_baixa_nao_dispara_antes_do_topo_dela(db, usuario):
    ex = _exercicio(db, "Levantamento terra romeno")
    s1 = _sessao(db, usuario.id, dias_atras=14)
    _serie(db, s1.id, ex.id, peso=60, reps=7, rir=None)
    s2 = _sessao(db, usuario.id, dias_atras=1)
    _serie(db, s2.id, ex.id, peso=60, reps=8, rir=None)  # ainda não bateu 9
    db.commit()

    assert "Levantamento terra romeno" not in _progression_names(db, usuario.id)


# --- Faixa ALTA: o sinal antigo disparava CEDO DEMAIS ------------------------
def test_faixa_alta_nao_dispara_antes_do_topo_dela(db, usuario):
    """Elevação lateral é prescrita 10-15 reps. O teto fixo antigo (12) mandava
    subir peso 3 repetições antes do topo real da faixa dela."""
    ex = _exercicio(db, "Elevação lateral na máquina")
    s1 = _sessao(db, usuario.id, dias_atras=14)
    _serie(db, s1.id, ex.id, peso=8, reps=11, rir=None)
    s2 = _sessao(db, usuario.id, dias_atras=1)
    _serie(db, s2.id, ex.id, peso=8, reps=12, rir=None)  # o teto ANTIGO disparava aqui
    db.commit()

    assert "Elevação lateral na máquina" not in _progression_names(db, usuario.id), (
        "disparou aos 12 reps — é o bug do teto fixo antigo, a faixa real vai até 15"
    )


def test_faixa_alta_dispara_no_topo_real(db, usuario):
    ex = _exercicio(db, "Elevação lateral na máquina")
    s1 = _sessao(db, usuario.id, dias_atras=14)
    _serie(db, s1.id, ex.id, peso=8, reps=14, rir=None)
    s2 = _sessao(db, usuario.id, dias_atras=1)
    _serie(db, s2.id, ex.id, peso=8, reps=15, rir=None)
    db.commit()

    assert "Elevação lateral na máquina" in _progression_names(db, usuario.id)


# --- RIR observado tem que comparar com o RIR-ALVO daquele exercício --------
def test_rir_abaixo_do_alvo_do_exercicio_barra_a_progressao(db, usuario):
    """Terra romeno tem RIR-alvo alto (é sistêmico e limitado pela lombar — Cap.
    XII). RIR observado 1 está bem abaixo disso: a folga que a prescrição exige
    não existe, mesmo tendo batido o topo da faixa de reps. Com a regra antiga
    ("folga = RIR >= 1"), RIR=1 passava — escondia justamente o caso em que a
    pessoa forçou demais um exercício que pede mais margem."""
    ex = _exercicio(db, "Levantamento terra romeno")
    s1 = _sessao(db, usuario.id, dias_atras=14)
    _serie(db, s1.id, ex.id, peso=60, reps=8, rir=None)
    s2 = _sessao(db, usuario.id, dias_atras=1)
    _serie(db, s2.id, ex.id, peso=60, reps=9, rir=1)  # bateu o topo, mas sem a folga exigida
    db.commit()

    assert "Levantamento terra romeno" not in _progression_names(db, usuario.id)


def test_rir_no_alvo_do_exercicio_libera_progressao(db, usuario):
    ex = _exercicio(db, "Levantamento terra romeno")
    s1 = _sessao(db, usuario.id, dias_atras=14)
    _serie(db, s1.id, ex.id, peso=60, reps=8, rir=None)
    s2 = _sessao(db, usuario.id, dias_atras=1)
    _serie(db, s2.id, ex.id, peso=60, reps=9, rir=3)  # RIR-alvo deste exercício é 3
    db.commit()

    assert "Levantamento terra romeno" in _progression_names(db, usuario.id)


def test_rir_nao_informado_ainda_conta_como_folga(db, usuario):
    """RIR fica atrás de 'mais opções' e não é obrigatório (regra 5 do produto).
    Quem não preenche não pode ficar sem o sinal de progressão por isso."""
    ex = _exercicio(db, "Elevação lateral na máquina")
    s1 = _sessao(db, usuario.id, dias_atras=14)
    _serie(db, s1.id, ex.id, peso=8, reps=14, rir=None)
    s2 = _sessao(db, usuario.id, dias_atras=1)
    _serie(db, s2.id, ex.id, peso=8, reps=15, rir=None)
    db.commit()

    assert "Elevação lateral na máquina" in _progression_names(db, usuario.id)
