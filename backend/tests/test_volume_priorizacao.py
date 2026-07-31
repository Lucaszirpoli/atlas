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


def test_financiador_cede_volume_pro_ponto_fraco(db):
    """A outra metade da equalização: quem não é prioridade CEDE. Sem isso o
    volume total só sobe e a recuperação (que é sistêmica) não fecha.

    O teste compara os DOIS mundos (com e sem ponto fraco) em vez de cobrar um
    número fixo, porque o piso de exercícios por sessão
    (training_brain.MIN_EXERCISES_PER_SESSION) impede que alguns músculos desçam
    até o piso da faixa: um dia inteiro vale mais que a última série de precisão
    do volume semanal. O que TEM que valer sempre é a direção — financiador cede,
    prioridade recebe — e é isso que está escrito aqui.
    """
    with usuario(db, handle="finansem") as sem_prioridade:
        workout_builder.build_and_save(db, sem_prioridade)
        base = series_por_musculo(db, sem_prioridade)
    with usuario(db, handle="financom", weak_points=["biceps"]) as com_prioridade:
        workout_builder.build_and_save(db, com_prioridade)
        priorizado = series_por_musculo(db, com_prioridade)

    cederam = [m for m in (M.BACK, M.CHEST, M.SHOULDERS, M.QUADS) if priorizado[m] < base[m]]
    assert len(cederam) >= 3, (
        "quase ninguém cedeu volume pro ponto fraco — a equalização não aconteceu: "
        f"{ {m.value: (base[m], priorizado[m]) for m in (M.BACK, M.CHEST, M.SHOULDERS, M.QUADS)} }"
    )
    maior_nao_prioritario = max(n for m, n in priorizado.items() if m is not M.BICEPS)
    assert priorizado[M.BICEPS] > maior_nao_prioritario


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


# --- O bloco de especialização tem PRAZO ----------------------------------
#
# Segurar o resto do corpo em manutenção é a troca certa por 4 a 8 semanas e
# errada pra sempre. Como "ponto fraco" é resposta de questionário (fica marcada
# até alguém mexer), sem prazo quem marcasse braço e esquecesse passaria um ano
# com costas e perna paradas — e concluiria que o app parou de funcionar.
from datetime import datetime, timedelta, timezone  # noqa: E402

from app.coaching import engine, training_brain  # noqa: E402


def _analise(weak_points, semanas):
    """Só a parte da análise que interessa aqui: os insights."""
    return engine._especializacao_insight(tuple(weak_points), semanas)


def test_bloco_novo_nao_cobra_nada(db):
    """Semana 1 de especialização não é hora de perguntar nada — a decisão
    acabou de ser tomada."""
    assert _analise(["biceps"], 0.0) is None
    assert _analise(["biceps"], training_brain.SPECIALIZATION_WEEKS - 1) is None


def test_bloco_vencido_devolve_a_decisao(db):
    ins = _analise(["biceps"], training_brain.SPECIALIZATION_WEEKS)
    assert ins is not None
    assert ins.severity == engine.SEV_ACTION
    assert ins.finding_key == "specialization:review"
    assert ins.adjustment["kind"] == "specialization"
    # O custo tem que estar dito em voz alta: é isso que faz a decisão ser
    # informada em vez de um botão sem contexto.
    assert "manutenção" in ins.detail


def test_sem_ponto_fraco_nao_existe_bloco(db):
    assert _analise([], 99) is None


def test_relogio_so_reinicia_quando_a_escolha_muda(db):
    """Reabrir e salvar as preferências sem mexer no ponto fraco NÃO pode zerar
    o relógio — senão bastaria salvar de novo pra a especialização nunca vencer,
    que é justamente o que este mecanismo existe pra impedir."""
    # O SQLite (dev) devolve a data SEM fuso; o Postgres (prod) devolve com.
    # Comparar o instante, e não o objeto, é o que faz este teste valer nos dois
    # — e é a mesma razão de training_brain.specialization_weeks normalizar a
    # data antes de fazer conta com ela.
    def instante(dt):
        return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt

    with usuario(db, handle="relogio", weak_points=["biceps"]) as u:
        perfil = u.profile
        antigo = datetime.now(timezone.utc) - timedelta(weeks=7)
        perfil.weak_points_since = antigo
        db.commit()

        agora = datetime.now(timezone.utc)
        training_brain.apply_weak_points(perfil, ["biceps"], agora)
        assert instante(perfil.weak_points_since) == antigo, "salvar a mesma escolha reiniciou o relógio"

        training_brain.apply_weak_points(perfil, ["triceps"], agora)
        assert instante(perfil.weak_points_since) == agora, "trocar de prioridade deveria reiniciar o relógio"

        training_brain.apply_weak_points(perfil, [], agora)
        assert perfil.weak_points_since is None, "sem ponto fraco não existe bloco em curso"


def test_relogio_sem_fuso_nao_quebra_a_conta(db):
    """Regressão de fuso: no SQLite a data volta naive e no Postgres volta aware.
    A conta de semanas tem que dar o mesmo dos dois lados — uma exceção aqui
    derrubaria a análise inteira do Coaching, não só a especialização."""
    agora = datetime.now(timezone.utc)
    naive = (agora - timedelta(weeks=7)).replace(tzinfo=None)
    aware = agora - timedelta(weeks=7)
    assert training_brain.specialization_weeks(naive, agora) == pytest.approx(
        training_brain.specialization_weeks(aware, agora)
    )
    assert training_brain.specialization_due(naive, agora)


def test_encerrar_o_bloco_devolve_o_volume(db):
    """Encerrar TEM que remontar o treino. Sem isso a pessoa aceita voltar ao
    normal e continua treinando as rotinas do bloco, com o corpo todo em 5
    séries — a escolha valeria no banco e não no treino."""
    with usuario(db, handle="encerra", weak_points=["biceps"]) as u:
        workout_builder.build_and_save(db, u)
        durante = series_por_musculo(db, u)
        # Pré-condição: durante o bloco o bíceps é quem manda no volume.
        assert durante[M.BICEPS] > durante[M.BACK]

        training_brain.apply_weak_points(u.profile, [], datetime.now(timezone.utc))
        db.flush()
        workout_builder.build_and_save(db, u)
        depois = series_por_musculo(db, u)

        # A conta é no TOTAL do resto do corpo, não num músculo escolhido a dedo:
        # com o piso de exercícios por sessão, um músculo que aparece todo dia
        # (costas) já estava acima do piso durante o bloco e não tem pra onde
        # subir. Quem se move é o conjunto.
        resto = lambda s: sum(n for m, n in s.items() if m is not M.BICEPS)  # noqa: E731
        assert resto(depois) > resto(durante), "o resto do corpo deveria voltar a crescer"
        assert depois[M.BICEPS] < durante[M.BICEPS], "bíceps deixa de ser prioridade"


# --- PISO DE EXERCÍCIOS POR SESSÃO ----------------------------------------
@pytest.mark.parametrize("sessao", ("curto", "medio", "longo"))
@pytest.mark.parametrize("dias", (3, 4, 5, 6))
@pytest.mark.parametrize("fracos", ([], ["biceps"], ["biceps", "triceps"]))
def test_nenhum_dia_sai_com_menos_de_cinco_exercicios(db, sessao, dias, fracos):
    """Regressão relatada pelo usuário treinando de verdade: "teve dia que ele
    colocou 3 exercícios só".

    A causa foi o preenchimento de volume podar vagas até o volume SEMANAL
    fechar, com piso por músculo (2×/semana) e nenhum piso por SESSÃO. Em 5 e 6
    dias o mesmo volume se espalhava fino e saíam dias de 1 a 3 exercícios — cada
    um coerente com o alvo da semana, e nenhum coerente com a ideia de um treino.

    A matriz inteira está aqui de propósito: os piores casos não eram o padrão,
    eram cantos específicos (6 dias + sessão curta + ponto fraco), que é
    exatamente o tipo de coisa que passa despercebida testando só o caminho
    comum.
    """
    with usuario(db, handle=f"piso{sessao[0]}{dias}{len(fracos)}",
                 weak_points=fracos, dias=dias) as u:
        u.profile.session_length = sessao
        db.commit()
        workout_builder.build_and_save(db, u)

        curtos = [
            (r.name, len(r.exercises))
            for r in db.execute(
                select(Routine).where(Routine.user_id == u.id, Routine.is_archived.is_(False))
            ).scalars()
            if len(r.exercises) < training_brain.MIN_EXERCISES_PER_SESSION
        ]
        assert not curtos, f"dia(s) abaixo do piso: {curtos}"


@pytest.mark.parametrize("dias", (4, 6))
def test_piso_de_sessao_nao_quebra_a_coerencia(db, dias):
    """O reforço acrescenta exercício DEPOIS de tudo — cobertura, equilíbrio,
    redundância e ordem continuam valendo no treino que sai."""
    with usuario(db, handle=f"pisocoer{dias}", weak_points=["biceps"], dias=dias) as u:
        u.profile.session_length = "curto"
        db.commit()
        resultado = workout_builder.build_and_save(db, u)
        assert resultado["is_coherent"], resultado["coherence_issues"]


def test_piso_de_sessao_nao_fura_o_teto_por_exercicio(db):
    """O dia cresce por EXERCÍCIO, nunca empilhando série: o teto de 3 séries de
    trabalho efetivas é o que protege da fadiga sem estímulo novo, e ele não é
    negociável nem pra fechar o piso do dia."""
    with usuario(db, handle="pisoteto", weak_points=["biceps"], dias=6) as u:
        u.profile.session_length = "curto"
        db.commit()
        workout_builder.build_and_save(db, u)
        sets = db.execute(
            select(RoutineExercise.target_sets)
            .join(Routine, Routine.id == RoutineExercise.routine_id)
            .where(Routine.user_id == u.id, Routine.is_archived.is_(False))
        ).scalars().all()
        assert max(sets) <= volume_landmarks.PER_EXERCISE_MAX
        assert min(sets) >= volume_landmarks.PER_EXERCISE_MIN


# --- PONTO FRACO NUNCA FICA SEM EXERCÍCIO ---------------------------------
@pytest.mark.parametrize("sessao", ("curto", "medio", "longo"))
@pytest.mark.parametrize("dias", (2, 3, 4, 5, 6))
@pytest.mark.parametrize(
    "fraco",
    ("chest", "back", "shoulders", "biceps", "triceps",
     "quads", "hamstrings", "glutes", "calves"),
)
def test_ponto_fraco_sempre_tem_exercicio_dedicado(db, sessao, dias, fraco):
    """A pergunta que o usuário fez: "existe risco de algum dia ficar sem
    exercício de algum grupo muscular?"

    A resposta tem que ser NÃO para todo músculo que a pessoa marcou como
    prioridade — marcar um músculo e receber zero exercício dele é o oposto de
    priorizar, e era o que acontecia em 21 das 195 combinações. Três causas
    diferentes, todas escondidas em cantos distintos:

      1. o corte por tempo rodava ANTES da promoção, então a vaga do ponto fraco
         já tinha sido cortada quando a promoção foi procurar o que promover;
      2. a promoção só reconhecia Pattern.ISO, e panturrilha é Pattern.CALF —
         panturrilha priorizada ficava sem exercício mesmo depois do conserto (1);
      3. com DOIS pontos fracos, só um pode abrir o dia; o outro voltava a ser
         cortado como se ninguém o tivesse marcado.

    A matriz inteira está aqui porque cada uma dessas apareceu num canto
    diferente, e nenhuma aparecia no caminho comum.
    """
    with usuario(db, handle=f"pf{sessao[0]}{dias}{fraco[:3]}", weak_points=[fraco], dias=dias) as u:
        u.profile.session_length = sessao
        db.commit()
        workout_builder.build_and_save(db, u)
        series = series_por_musculo(db, u)
        assert series[M(fraco)] > 0, (
            f"{fraco} foi marcado como ponto fraco e terminou a semana com ZERO séries "
            f"({sessao}, {dias} dias)"
        )


@pytest.mark.parametrize("dias", (2, 4, 6))
def test_dois_pontos_fracos_juntos_ambos_recebem(db, dias):
    """Só um músculo pode ABRIR o dia — mas os dois marcados têm que receber
    exercício. O segundo não pode "perder" pro primeiro."""
    with usuario(db, handle=f"dois{dias}", weak_points=["biceps", "triceps"], dias=dias) as u:
        u.profile.session_length = "curto"
        db.commit()
        workout_builder.build_and_save(db, u)
        series = series_por_musculo(db, u)
        assert series[M.BICEPS] > 0 and series[M.TRICEPS] > 0, (
            f"bíceps={series[M.BICEPS]} tríceps={series[M.TRICEPS]} — os dois foram marcados"
        )
