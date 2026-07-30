"""O volume que a pessoa RECEBE, não o que o coach calculou.

Estes testes existem por causa de uma queixa específica do usuário: "eu posso
trocar os meus pontos fracos e ele não muda praticamente nada do treino". A
priorização existia — `volume_landmarks.weekly_plan` reduzia o alvo dos
músculos sem prioridade e subia o do ponto fraco — e mesmo assim não chegava no
treino, porque duas coisas a desfaziam no caminho:

  1. as duas faixas (base e ponto fraco) partiam do PISO na semana 1, então na
     prática todo mundo tinha alvo 5 e o ponto fraco tinha 8;
  2. nenhuma vaga vai abaixo de PER_EXERCISE_MIN séries, então um músculo com 5
     vagas e alvo 5 saía com 10 séries — o dobro do alvo, e mais volume que o
     próprio ponto fraco.

Testar `weekly_plan` isolado NÃO pega isso: os dois bugs estavam entre o alvo e
a rotina salva. Por isso aqui é ponta a ponta, medindo `target_sets` do que foi
gravado no banco.
"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager

import pytest
from sqlalchemy import delete, select

from app.coaching import volume_landmarks, workout_builder
from app.core.db import SessionLocal
from app.models.coaching_technique_cue import CoachingTechniqueCue
from app.models.exercise import Exercise
from app.models.exercise import MuscleGroup as M
from app.models.routine import Routine, RoutineExercise
from app.models.user import Plan, User
from app.models.user_profile import (
    ActivityLevel,
    BiologicalSex,
    ExperienceLevel,
    Goal,
    TrainingLocation,
    UserProfile,
)


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    if s.execute(select(Exercise.id).where(Exercise.is_hidden.is_(False)).limit(1)).first() is None:
        s.close()
        pytest.skip("biblioteca de exercícios não semeada neste banco")
    yield s
    s.close()


@contextmanager
def usuario(db, *, handle: str, weak_points: list[str] | None = None, dias: int = 4):
    """Um usuário Pro descartável com perfil completo. Some no fim do teste —
    estes testes rodam contra o banco de dev, que é o único com a biblioteca."""
    email = f"__tmp_vol_{handle}__@teste.local"

    def limpar():
        u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if u is None:
            return
        rids = [r.id for r in db.execute(select(Routine).where(Routine.user_id == u.id)).scalars()]
        if rids:
            db.execute(delete(RoutineExercise).where(RoutineExercise.routine_id.in_(rids)))
            db.execute(delete(Routine).where(Routine.id.in_(rids)))
        db.execute(delete(CoachingTechniqueCue).where(CoachingTechniqueCue.user_id == u.id))
        db.execute(delete(UserProfile).where(UserProfile.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
        db.commit()

    limpar()
    u = User(email=email, handle=f"__tmp_v_{handle}__", display_name="T",
             password_hash="x", plan=Plan.PRO)
    db.add(u)
    db.flush()
    db.add(UserProfile(
        user_id=u.id, age=30, height_cm=180,
        biological_sex=BiologicalSex.MALE, activity_level=ActivityLevel.MODERATE,
        training_location=TrainingLocation.ACADEMIA_COMPLETA,
        experience_level=ExperienceLevel.INTERMEDIARIO, goal=Goal.HIPERTROFIA,
        training_days_per_week=dias, session_length="longo",
        # Técnica avançada desligada: ela desconta do teto de séries por
        # exercício (muscle round e myo-reps valem 2), e aqui o que está sendo
        # medido é a DISTRIBUIÇÃO do volume, não a densidade.
        allow_advanced_techniques=False, periodization="auto", wants_cardio=False,
        weak_points=list(weak_points or []),
    ))
    db.commit()
    try:
        yield u
    finally:
        limpar()


def series_por_musculo(db, user) -> Counter:
    """Séries de trabalho semanais que a pessoa REALMENTE recebeu, por músculo."""
    linhas = db.execute(
        select(Exercise.primary_muscle_group, RoutineExercise.target_sets)
        .join(RoutineExercise, RoutineExercise.exercise_id == Exercise.id)
        .join(Routine, Routine.id == RoutineExercise.routine_id)
        .where(Routine.user_id == user.id, Routine.is_archived.is_(False))
    ).all()
    total: Counter = Counter()
    for musculo, sets in linhas:
        total[musculo] += sets
    return total


def exercicios_por_musculo(db, user) -> Counter:
    linhas = db.execute(
        select(Exercise.primary_muscle_group)
        .join(RoutineExercise, RoutineExercise.exercise_id == Exercise.id)
        .join(Routine, Routine.id == RoutineExercise.routine_id)
        .where(Routine.user_id == user.id, Routine.is_archived.is_(False))
    ).scalars().all()
    return Counter(linhas)


# --- O que o usuário reclamou ---------------------------------------------
def test_ponto_fraco_recebe_mais_volume_que_todo_mundo(db):
    """A regressão principal. Com bíceps como ponto fraco, bíceps tem que ser o
    músculo com MAIS séries na semana — antes ele empatava com tríceps e recebia
    menos que costas e ombro."""
    with usuario(db, handle="fraco", weak_points=["biceps"]) as u:
        workout_builder.build_and_save(db, u)
        series = series_por_musculo(db, u)

        biceps = series[M.BICEPS]
        assert biceps >= volume_landmarks.WEAK_MIN, (
            f"ponto fraco com {biceps} séries, abaixo do piso de ponto fraco "
            f"({volume_landmarks.WEAK_MIN})"
        )
        outros = {m: n for m, n in series.items() if m is not M.BICEPS}
        maior = max(outros.items(), key=lambda kv: kv[1])
        assert biceps > maior[1], (
            f"bíceps é ponto fraco e recebeu {biceps} séries, mas {maior[0].value} recebeu {maior[1]}"
        )


def test_trocar_o_ponto_fraco_muda_o_treino(db):
    """O sintoma que o usuário descreveu, em forma de teste: dois perfis
    idênticos, só o ponto fraco diferente — o volume tem que sair diferente."""
    with usuario(db, handle="pfa", weak_points=["biceps"]) as a:
        workout_builder.build_and_save(db, a)
        volume_a = series_por_musculo(db, a)
    with usuario(db, handle="pfb", weak_points=["quads"]) as b:
        workout_builder.build_and_save(db, b)
        volume_b = series_por_musculo(db, b)

    assert volume_a[M.BICEPS] > volume_b[M.BICEPS]
    assert volume_b[M.QUADS] > volume_a[M.QUADS]


def test_financiador_e_segurado_perto_do_piso(db):
    """A outra metade da equalização: quem não é prioridade CEDE. Sem isso o
    volume total só sobe e a recuperação (que é sistêmica) não fecha."""
    with usuario(db, handle="finan", weak_points=["biceps"]) as u:
        workout_builder.build_and_save(db, u)
        series = series_por_musculo(db, u)

        # +1 de folga: a poda respeita cobertura regional e equilíbrio da semana,
        # então um músculo pode ficar uma série acima do piso por proteção.
        teto = volume_landmarks.BASE_MIN + 1
        for musculo in (M.BACK, M.CHEST, M.SHOULDERS):
            assert series[musculo] <= teto, (
                f"{musculo.value} devia estar segurado perto de {volume_landmarks.BASE_MIN} "
                f"séries e está com {series[musculo]}"
            )


def test_sem_ponto_fraco_ninguem_e_segurado(db):
    """A redução é o preço de uma prioridade. Sem ponto fraco nenhum, os músculos
    ficam na faixa-base — não no piso dela."""
    with usuario(db, handle="semfraco") as u:
        workout_builder.build_and_save(db, u)
        series = series_por_musculo(db, u)
        for musculo in (M.BACK, M.CHEST, M.QUADS):
            assert series[musculo] > volume_landmarks.BASE_MIN, (
                f"{musculo.value} ficou no piso ({series[musculo]}) sem ninguém pra financiar"
            )


# --- As travas que a priorização não pode atropelar ------------------------
def test_teto_de_tres_series_por_exercicio(db):
    """Volume a mais vira EXERCÍCIO a mais, nunca série empilhada: passar do teto
    por exercício é fadiga sem estímulo novo."""
    with usuario(db, handle="teto", weak_points=["biceps", "triceps"]) as u:
        workout_builder.build_and_save(db, u)
        sets = db.execute(
            select(RoutineExercise.target_sets)
            .join(Routine, Routine.id == RoutineExercise.routine_id)
            .where(Routine.user_id == u.id, Routine.is_archived.is_(False))
        ).scalars().all()
        assert sets
        assert max(sets) <= volume_landmarks.PER_EXERCISE_MAX
        assert min(sets) >= volume_landmarks.PER_EXERCISE_MIN


def test_frequencia_minima_de_duas_vezes_por_semana(db):
    """Regra 6 do produto: nada de bro-split. A poda dos financiadores é
    agressiva de propósito — não pode ser agressiva a ponto de deixar um músculo
    com um exercício só na semana."""
    with usuario(db, handle="freq", weak_points=["biceps", "triceps"]) as u:
        workout_builder.build_and_save(db, u)
        vagas = exercicios_por_musculo(db, u)
        for musculo, n in vagas.items():
            assert n >= 2, f"{musculo.value} ficou com {n} exercício(s) na semana"


def test_treino_priorizado_continua_coerente(db):
    """A regra de coerência global (as 8 perguntas) vale igual quando o volume é
    remanejado — cobertura, equilíbrio e ordem não são negociáveis pela
    priorização."""
    for fraco in (["biceps"], ["quads"], ["back"], ["biceps", "triceps"]):
        with usuario(db, handle="coer" + fraco[0], weak_points=fraco) as u:
            resultado = workout_builder.build_and_save(db, u)
            assert resultado["is_coherent"], (fraco, resultado["coherence_issues"])


def test_priorizacao_e_explicada_pra_pessoa(db):
    """Uma diferença que a pessoa não consegue ler continua sendo invisível — foi
    metade da queixa original."""
    with usuario(db, handle="nota", weak_points=["biceps"]) as u:
        resultado = workout_builder.build_and_save(db, u)
        assert resultado["priority_note"], "a priorização precisa sair em texto"
        assert "bíceps" in resultado["priority_note"].lower()


def nomes_dos_exercicios(db, user) -> list[str]:
    return sorted(
        db.execute(
            select(Exercise.name)
            .join(RoutineExercise, RoutineExercise.exercise_id == Exercise.id)
            .join(Routine, Routine.id == RoutineExercise.routine_id)
            .where(Routine.user_id == user.id, Routine.is_archived.is_(False))
        ).scalars().all()
    )


def test_dois_usuarios_iguais_recebem_treinos_diferentes(db):
    """Mesmas respostas, mesmo plano — exercícios diferentes. É psicológico e é
    de propósito: o treino tem que parecer dela.

    Os dois usuários existem AO MESMO TEMPO de propósito. Criando um depois de
    apagar o outro, o SQLite recicla o rowid — os dois nasciam com o mesmo id, a
    semente saía igual e o teste passava a impressão de que a variação não
    funcionava quando na verdade era o banco reaproveitando o número.
    """
    with usuario(db, handle="gemeoa", weak_points=["biceps"]) as a:
        with usuario(db, handle="gemeob", weak_points=["biceps"]) as b:
            assert a.id != b.id, "pré-condição do teste: ids diferentes"
            workout_builder.build_and_save(db, a)
            workout_builder.build_and_save(db, b)

            assert nomes_dos_exercicios(db, a) != nomes_dos_exercicios(db, b), (
                "os dois receberam exatamente os mesmos exercícios"
            )
            # ... mas o PLANO é o mesmo: mesma prioridade, mesmo volume por músculo.
            assert series_por_musculo(db, a) == series_por_musculo(db, b), (
                "a variação é de exercício, não de volume — os dois têm a mesma prioridade"
            )


def test_remontar_o_treino_nao_troca_os_exercicios(db):
    """A variação é por PESSOA, não por montagem. Se ela fosse por montagem, a
    pessoa refaria o treino e veria tudo mudar sem ter pedido nada."""
    with usuario(db, handle="remonta", weak_points=["biceps"]) as u:
        workout_builder.build_and_save(db, u)
        primeira = nomes_dos_exercicios(db, u)
        workout_builder.build_and_save(db, u)
        assert nomes_dos_exercicios(db, u) == primeira
