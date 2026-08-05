"""A troca de exercício da prévia do treino.

O risco desta funcionalidade não é ela não funcionar — é ela funcionar demais.
Um botão que troca exercício sem passar pelas regras vira uma porta lateral pra
montar, clique a clique, exatamente o treino que a regra mestra reprova: três
exercícios da mesma função, um isolador ocupando a vaga do composto que abre o
dia, ou um exercício que a preferência da pessoa tinha excluído. Os testes aqui
cobram o substituto pelos mesmos critérios da montagem.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import delete, select

from app.ai.exercise_taxonomy import taxon_for_exercise, tier_rank
from app.coaching import exercise_swap, workout_builder
from app.core.db import SessionLocal
from app.models.exercise import Exercise
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
def usuario_com_treino(db, *, handle: str, exercise_prefs: list[str] | None = None):
    """Uma pessoa com o treino do coach já montado — que é o estado em que a
    troca acontece de verdade (a prévia é de uma rotina que o coach montou)."""
    email = f"__tmp_swap_{handle}__@teste.local"

    def limpar():
        u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if u is None:
            return
        rids = [r.id for r in db.execute(select(Routine).where(Routine.user_id == u.id)).scalars()]
        if rids:
            db.execute(delete(RoutineExercise).where(RoutineExercise.routine_id.in_(rids)))
            db.execute(delete(Routine).where(Routine.id.in_(rids)))
        db.execute(delete(UserProfile).where(UserProfile.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
        db.commit()

    limpar()
    u = User(email=email, handle=f"__tmp_s_{handle}__", display_name="T",
             password_hash="x", plan=Plan.PRO)
    db.add(u)
    db.flush()
    db.add(UserProfile(
        user_id=u.id, age=30, height_cm=180,
        biological_sex=BiologicalSex.MALE, activity_level=ActivityLevel.MODERATE,
        training_location=TrainingLocation.ACADEMIA_COMPLETA,
        experience_level=ExperienceLevel.INTERMEDIARIO, goal=Goal.HIPERTROFIA,
        training_days_per_week=4, session_length="longo",
        allow_advanced_techniques=False, periodization="auto",
        exercise_prefs=list(exercise_prefs or []),
    ))
    db.commit()
    workout_builder.build_and_save(db, u)
    db.refresh(u)
    try:
        yield u
    finally:
        limpar()


def rotinas(db, user) -> list[Routine]:
    return list(
        db.execute(
            select(Routine).where(Routine.user_id == user.id, Routine.is_archived.is_(False))
        ).scalars()
    )


def todas_as_vagas(db, user) -> list[tuple[Routine, RoutineExercise]]:
    return [(r, re) for r in rotinas(db, user) for re in r.exercises]


def test_substituto_existe_para_todo_exercicio_do_treino(db):
    """O botão não pode ser um beco: se ele aparece na prévia, tem que resolver.
    Onde a biblioteca não tiver saída, o app avisa — mas isso precisa ser a
    exceção, não a regra."""
    with usuario_com_treino(db, handle="cobertura") as u:
        vagas = todas_as_vagas(db, u)
        assert vagas
        sem_saida = [
            re.exercise.name
            for r, re in vagas
            if exercise_swap.melhor_substituto(db, u, re, list(r.exercises)) is None
        ]
        assert len(sem_saida) <= 1, f"exercícios sem substituto: {sem_saida}"


def test_substituto_preserva_musculo_e_papel(db):
    """Trocar exercício é trocar exercício — não é trocar o que a vaga faz no
    treino. Um composto que vira isolador mudaria a ORDEM da sessão, não só o
    nome do exercício."""
    with usuario_com_treino(db, handle="papel") as u:
        for r, re in todas_as_vagas(db, u):
            novo = exercise_swap.melhor_substituto(db, u, re, list(r.exercises))
            if novo is None:
                continue
            antes, depois = taxon_for_exercise(re.exercise), taxon_for_exercise(novo)
            assert novo.primary_muscle_group == re.exercise.primary_muscle_group
            assert depois.order_class == antes.order_class, (
                f"{re.exercise.name} -> {novo.name}: mudou a classe de ordem da vaga"
            )
            assert novo.id != re.exercise_id


def test_substituto_nunca_repete_o_que_ja_esta_no_treino(db):
    """Volume novo, não a mesma coisa de novo (Princípio 4)."""
    with usuario_com_treino(db, handle="repete") as u:
        for r, re in todas_as_vagas(db, u):
            novo = exercise_swap.melhor_substituto(db, u, re, list(r.exercises))
            if novo is None:
                continue
            ids_do_dia = {x.exercise_id for x in r.exercises}
            assert novo.id not in ids_do_dia


def test_substituto_respeita_a_preferencia_da_pessoa(db):
    """Quem marcou "sem agachamento livre" não pode receber agachamento livre por
    ter apertado trocar. A preferência é filtro na montagem e continua sendo aqui."""
    with usuario_com_treino(db, handle="pref", exercise_prefs=["sem_agachamento_livre"]) as u:
        proibidas = ("agachamento livre", "agachamento com barra", "back squat", "front squat")
        for r, re in todas_as_vagas(db, u):
            novo = exercise_swap.melhor_substituto(db, u, re, list(r.exercises))
            if novo is None:
                continue
            nome = novo.name.lower()
            assert not any(p in nome for p in proibidas), f"a troca ofereceu {novo.name}"


def test_troca_nao_rebaixa_o_tier_sem_motivo(db):
    """Tier A/B/C não é exercício ruim, mas descer de tier tem que ter motivo (o
    de cima acabou), nunca ser o caminho preferido. Como o substituto sai da mesma
    classe de ordem e do mesmo músculo, ele não pode ser pior que o segundo melhor
    daquele grupo."""
    with usuario_com_treino(db, handle="tier") as u:
        for r, re in todas_as_vagas(db, u):
            novo = exercise_swap.melhor_substituto(db, u, re, list(r.exercises))
            if novo is None:
                continue
            atual = taxon_for_exercise(re.exercise)
            escolhido = taxon_for_exercise(novo)
            assert tier_rank(escolhido.tier) <= tier_rank(atual.tier) + 1, (
                f"{re.exercise.name} ({atual.tier}) -> {novo.name} ({escolhido.tier}): "
                "queda de tier grande demais pra uma troca"
            )


def test_troca_e_estavel(db):
    """Perguntar duas vezes dá a mesma resposta — a troca não sorteia na hora,
    senão a pessoa apertaria de novo até gostar e a regra viraria decoração."""
    with usuario_com_treino(db, handle="estavel") as u:
        for r, re in todas_as_vagas(db, u)[:5]:
            a = exercise_swap.melhor_substituto(db, u, re, list(r.exercises))
            b = exercise_swap.melhor_substituto(db, u, re, list(r.exercises))
            assert (a and a.id) == (b and b.id)


def test_troca_explica_o_motivo(db):
    """A pessoa precisa entender POR QUE veio esse exercício, senão a troca é
    mágica — e mágica não constrói confiança no coach."""
    with usuario_com_treino(db, handle="motivo") as u:
        r, re = todas_as_vagas(db, u)[0]
        novo = exercise_swap.melhor_substituto(db, u, re, list(r.exercises))
        assert novo is not None
        motivo = exercise_swap.explicar(re.exercise, novo)
        assert novo.name in motivo and re.exercise.name in motivo
