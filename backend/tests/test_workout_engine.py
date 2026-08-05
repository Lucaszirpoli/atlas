"""O motor de montagem contra a REGRA MESTRA.

Estes testes existem porque os erros que importam aqui são silenciosos: uma vaga
que não preenche faz o treino sair com um exercício a menos e ninguém percebe; um
blueprint torto faz a semana desequilibrar sem erro nenhum. Foi exatamente assim
que os dois bugs desta leva apareceram — a vaga de "segundo estímulo" vazia no
dia de inferior, e a panturrilha antes das roscas no Torso/Limbs.

Dependem da biblioteca curada estar semeada no banco de dev (é o único ambiente
com dados que este projeto tem). Sem ela, os testes são pulados em vez de falhar
por um motivo que não é o deles.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.ai import plan_review, session_blueprints as bp
from app.ai.exercise_taxonomy import ORDER_MINOR, Pattern, Tier, order_class_for_pattern
from app.ai.methods import TORSO_LIMBS_SPLIT, coach_custom_spec, coach_split_for
from app.ai.methods_engine import add_accessory_slot, build_plan
from app.core.db import SessionLocal
from app.models.exercise import Exercise
from app.models.exercise import MuscleGroup as M

FREQUENCIAS = (2, 3, 4, 5, 6)
OBJETIVOS = ("hipertrofia", "emagrecimento", "recomposicao", "manutencao", "performance")


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    visiveis = s.execute(
        select(Exercise.id).where(Exercise.is_hidden.is_(False), Exercise.is_custom.is_(False)).limit(1)
    ).first()
    if visiveis is None:
        s.close()
        pytest.skip("biblioteca de exercícios não semeada neste banco")
    yield s
    s.close()


def _plan(db, *, dias=4, objetivo="hipertrofia", **kw):
    spec = coach_custom_spec(objetivo, "intermediario")
    return spec, build_plan(db, spec, available_days=dias, **kw)


# --- Coerência global ------------------------------------------------------
@pytest.mark.parametrize("dias", FREQUENCIAS)
@pytest.mark.parametrize("objetivo", OBJETIVOS)
def test_todo_plano_passa_na_coerencia_global(db, dias, objetivo):
    spec, plan = _plan(db, dias=dias, objetivo=objetivo)
    assert plan_review.review(plan, method=spec) == []


@pytest.mark.parametrize("dias", FREQUENCIAS)
def test_nenhuma_vaga_fica_vazia(db, dias):
    """Toda vaga do blueprint tem que virar exercício. A vaga que não preenche
    não dá erro — ela simplesmente desaparece do treino."""
    _, plan = _plan(db, dias=dias)
    esperado = sum(len(bp.blueprint_for(f)) for f in coach_split_for(dias))
    real = sum(len(s.slots) for s in plan.sessions)
    assert real == esperado, f"{esperado - real} vaga(s) do blueprint não foram preenchidas"


@pytest.mark.parametrize("dias", FREQUENCIAS)
def test_todo_foco_do_split_tem_blueprint(db, dias):
    for foco in coach_split_for(dias):
        assert foco in bp.BLUEPRINTS, f"foco '{foco}' cairia no blueprint padrão"


def test_nao_existe_split_de_7_dias():
    """7 dias não existe: sem folga não há recuperação."""
    from app.ai.methods import _COACH_SPLITS

    assert 7 not in _COACH_SPLITS
    assert max(_COACH_SPLITS) == 6


# --- Princípio 2 / regra de substituição ----------------------------------
def test_abre_a_sessao_com_tier_alto(db):
    """A vaga de composto prioritário recebe primeira escolha (S), não sobra."""
    from app.ai.exercise_taxonomy import taxon_for

    _, plan = _plan(db, dias=4)
    for s in plan.sessions:
        t = taxon_for(s.slots[0].exercise_name)
        assert t.tier in (Tier.S, Tier.A), f"{s.focus} abre com tier {t.tier}: {s.slots[0].exercise_name}"


def test_substituicao_quando_a_preferencia_exclui_tudo(db):
    """Quem marca "evitar acima da cabeça" perde todo desenvolvimento. A vaga de
    empurrar vertical não pode ficar vazia — tem que virar um empurrar horizontal
    (é o que um treinador faria), senão a semana desequilibra por causa de uma
    preferência legítima."""
    spec, plan = _plan(db, dias=4, exercise_prefs=["sem_acima_da_cabeca"])
    nomes = [sl.exercise_name.lower() for s in plan.sessions for sl in s.slots]
    assert not any("desenvolvimento" in n for n in nomes), "entrou desenvolvimento contra a preferência"
    assert plan_review.review(plan, method=spec) == []


def test_preferencia_de_maquinas_e_respeitada(db):
    from app.models.exercise import Equipment

    _, plan = _plan(db, dias=4, exercise_prefs=["maquinas"])
    ids = [sl.exercise_id for s in plan.sessions for sl in s.slots]
    equipamentos = [db.get(Exercise, i).equipment for i in ids]
    estaveis = sum(1 for e in equipamentos if e in (Equipment.MACHINE, Equipment.CABLE, Equipment.SMITH_MACHINE))
    assert estaveis / len(equipamentos) >= 0.8, "maioria dos exercícios deveria ser máquina/cabo"


# --- Princípio 3: ordem ----------------------------------------------------
@pytest.mark.parametrize("dias", FREQUENCIAS)
def test_musculo_menor_fecha_o_treino(db, dias):
    """Panturrilha, abdutor/adutor e core só depois de todo o resto."""
    _, plan = _plan(db, dias=dias)
    for s in plan.sessions:
        ordens = [order_class_for_pattern(Pattern(sl.pattern)) for sl in s.slots]
        menores = [i for i, o in enumerate(ordens) if o >= ORDER_MINOR]
        if menores:
            assert menores == list(range(min(menores), len(ordens))), (
                f"{s.focus}: músculo menor no meio do treino "
                f"({[sl.exercise_name for sl in s.slots]})"
            )


@pytest.mark.parametrize("dias", FREQUENCIAS)
def test_sessao_abre_com_composto(db, dias):
    _, plan = _plan(db, dias=dias)
    for s in plan.sessions:
        assert s.slots[0].is_compound, f"{s.focus} abre com isolado: {s.slots[0].exercise_name}"


# --- Princípio 4: redundância ---------------------------------------------
@pytest.mark.parametrize("dias", FREQUENCIAS)
def test_sem_redundancia_de_funcao(db, dias):
    _, plan = _plan(db, dias=dias)
    assert plan_review.redundancias(plan) == []


def test_o_exemplo_ruim_da_spec_seria_reprovado():
    """Prova que o detector funciona: os 3 supinos retos que a spec dá como
    exemplo de desperdício de volume têm que ser pegos."""
    from app.ai.methods_engine import PlannedSession, PlannedSlot, WorkoutPlan

    def slot(nome, ordem):
        return PlannedSlot(
            order=ordem, muscle_group="chest", is_compound=True, exercise_id=ordem,
            exercise_name=nome, sets="3", reps="8-12", tempo=None, rest_seconds="90", rir="1-2",
            pattern=Pattern.PUSH_H.value, region="peito esternal",
        )

    plan = WorkoutPlan(
        method_key="t", method_name="t", author="t", days_per_week=1, mesocycle=None,
        deload_rule=None, progression_rule="", phase_context=None,
        sessions=[PlannedSession(0, "Dia 1", "superior a", None, [
            slot("Supino reto com barra", 1), slot("Supino reto no Smith", 2), slot("Chest press", 3),
        ])],
    )
    assert plan_review.redundancias(plan), "as 3 mesmas funções deveriam ser detectadas"


# --- Princípio 6: cobertura regional --------------------------------------
@pytest.mark.parametrize("dias", FREQUENCIAS)
def test_cobertura_regional_da_semana(db, dias):
    _, plan = _plan(db, dias=dias)
    assert plan_review.regioes_descobertas(plan) == []


# --- Tempo por sessão -----------------------------------------------------
@pytest.mark.parametrize("alvo", (5, 6, 8))
def test_recorte_por_tempo_preserva_o_essencial(db, alvo):
    """O recorte por tempo tira acessório, nunca a abertura do treino."""
    spec, plan = _plan(db, dias=4, session_target=alvo)
    for s in plan.sessions:
        assert len(s.slots) <= max(alvo, 7)
        assert s.slots[0].is_compound


@pytest.mark.parametrize("alvo", (5, 6, 8))
@pytest.mark.parametrize("dias", FREQUENCIAS)
def test_recorte_por_tempo_nao_zera_musculo_da_semana(db, dias, alvo):
    """NENHUM músculo que a divisão treina pode sair da semana por falta de tempo.

    Este é o teste do bug que um usuário relatou na v53: 4 dias, upper/lower,
    tempo Médio, e o treino saía sem UMA panturrilha, sem UM abdominal e sem UM
    tríceps direto na semana inteira. O corte era por sessão e olhava só a
    `priority`, então a vaga do fim caía sempre — e a vaga do fim é panturrilha
    nos dois dias de inferior e abdômen/tríceps nos dois de superior.

    Nada reclamava, e é por isso que este teste existe do lado do
    `plan_review.musculos_perdidos`: a coerência global só cobrava REGIÃO de
    músculo que o treino treina, então um músculo com zero vaga era invisível
    pras oito perguntas.
    """
    _, plan = _plan(db, dias=dias, session_target=alvo)
    assert plan_review.musculos_perdidos(plan) == []


@pytest.mark.parametrize("alvo", (5, 6, 8))
@pytest.mark.parametrize("dias", FREQUENCIAS)
def test_plano_entregue_e_coerente(db, dias, alvo):
    """A coerência é cobrada do treino ENTREGUE, não do rascunho.

    `build_plan` sozinho pode terminar devendo uma região quando a geometria não
    fecha — em 4 dias × 5 exercícios, as duas sessões de superior têm 10 vagas
    pra 11 exigências (2 por peito/costas/ombro/bíceps/tríceps + abdômen), e
    alguma coisa TEM que ceder. O que cede é a região, porque ela é a única
    lacuna que tem conserto mecânico: `workout_builder._reparar_cobertura` roda
    logo depois e pede exatamente a região que faltou. É esse plano, o que a
    pessoa recebe, que precisa passar nas oito perguntas.
    """
    spec, plan = _plan(db, dias=dias, session_target=alvo)
    for musculo, regiao in plan_review.regioes_descobertas(plan):
        add_accessory_slot(db, plan, musculo, region=regiao, max_per_session=9)
    assert plan_review.review(plan, method=spec) == []


def test_recorte_corta_o_acessorio_antes_do_essencial():
    """Com o alvo real mais apertado (5 = sessão curta), o que sai é acessório."""
    for foco, blueprint in bp.BLUEPRINTS.items():
        recortado = bp.fit_to_target(blueprint, 5)
        essenciais_antes = sum(1 for s in blueprint if s.priority == 1)
        essenciais_depois = sum(1 for s in recortado if s.priority == 1)
        # só perde essencial se o blueprint tiver mais essenciais que o alvo
        perda_aceitavel = max(0, essenciais_antes - 5)
        assert essenciais_antes - essenciais_depois <= perda_aceitavel, foco
        assert len(recortado) == min(5, len(blueprint)), foco


def test_recorte_agressivo_preserva_a_abertura_do_treino():
    """Mesmo num alvo absurdo, a vaga 1 sobrevive e a ordem é preservada.

    Quem abre é o composto prioritário na maioria dos dias e a vaga de prioridade
    no dia de membros (onde o braço — o motivo da divisão Torso/Limbs existir —
    abre o treino descansado). As duas são aberturas legítimas; o que o recorte
    não pode fazer é entregar um dia que começa por um acessório."""
    for foco, blueprint in bp.BLUEPRINTS.items():
        recortado = bp.fit_to_target(blueprint, 1)
        assert recortado == [blueprint[0]], foco
        assert recortado[0].role in (bp.ROLE_PRIMARY, bp.ROLE_PRIORITY_OPEN), foco


def test_recorte_preserva_a_ordem_original():
    for foco, blueprint in bp.BLUEPRINTS.items():
        for alvo in (2, 4, 6):
            recortado = bp.fit_to_target(blueprint, alvo)
            posicoes = [blueprint.index(s) for s in recortado]
            assert posicoes == sorted(posicoes), f"{foco} alvo {alvo}: ordem embaralhada"


# --- Torso / Limbs --------------------------------------------------------
@pytest.mark.parametrize("fraco", ("biceps", "triceps", "calves"))
def test_ponto_fraco_menor_troca_para_torso_limbs(fraco):
    assert coach_split_for(4, [fraco]) == TORSO_LIMBS_SPLIT


@pytest.mark.parametrize("fraco", ("chest", "back", "quads", "glutes"))
def test_ponto_fraco_grande_mantem_upper_lower(fraco):
    assert coach_split_for(4, [fraco]) != TORSO_LIMBS_SPLIT


def test_torso_limbs_passa_na_coerencia(db):
    spec, plan = _plan(db, dias=4, weak_points=[M.BICEPS])
    assert [s.focus for s in plan.sessions] == TORSO_LIMBS_SPLIT
    assert plan_review.review(plan, method=spec) == []


# --- Ponto fraco muda a ordem --------------------------------------------
def test_ponto_fraco_abre_a_sessao(db):
    """Costas como ponto fraco: o dia de superior tem que ABRIR puxando, não
    empurrando — quem é prioridade pega a pessoa inteira."""
    _, plan = _plan(db, dias=4, weak_points=[M.BACK])
    superiores = [s for s in plan.sessions if s.focus.startswith("superior")]
    assert superiores
    for s in superiores:
        assert s.slots[0].muscle_group == M.BACK.value, (
            f"{s.focus} abre com {s.slots[0].exercise_name}, esperado um exercício de costas"
        )


# --- Os treinos de REFERÊNCIA do usuário ---------------------------------
def test_superior_a_reproduz_o_template_de_referencia(db):
    """O UPPER A que o usuário passou como template: 2 empurradas horizontais,
    1 puxada horizontal, 1 puxada vertical, 1 isolamento de ombro, 1 de tríceps
    e 1 de bíceps — nesta ordem de papéis. Fecha com abdômen (minor, priority=3
    — cai fora primeiro se o tempo de sessão apertar)."""
    _, plan = _plan(db, dias=4)
    s = next(x for x in plan.sessions if x.focus == "superior a")
    assert [sl.pattern for sl in s.slots] == [
        Pattern.PUSH_H.value,
        Pattern.PULL_H.value,
        Pattern.PUSH_H.value,
        Pattern.PULL_V.value,
        Pattern.ISO.value,
        Pattern.ISO.value,
        Pattern.ISO.value,
        Pattern.CORE.value,
    ]
    assert [sl.muscle_group for sl in s.slots[4:]] == ["shoulders", "triceps", "biceps", "abs"]
    # as duas empurradas horizontais são em regiões DIFERENTES do peito — é o que
    # as torna complementares em vez de redundantes.
    assert s.slots[0].region != s.slots[2].region


def test_inferior_a_reproduz_o_template_de_referencia(db):
    """O LOWER A de referência: dominante de joelho, dobradiça de quadril,
    segundo dominante de joelho, flexão de joelho, glúteo, abdutor, panturrilha."""
    _, plan = _plan(db, dias=4)
    s = next(x for x in plan.sessions if x.focus == "inferior a")
    assert [sl.pattern for sl in s.slots] == [
        Pattern.KNEE.value,
        Pattern.HIP.value,
        Pattern.KNEE.value,
        Pattern.KNEE_FLEX.value,
        Pattern.HIP.value,
        Pattern.ABDUCTION.value,
        Pattern.CALF.value,
    ]


def test_segunda_passagem_do_ppl_varia_os_exercicios(db):
    """6 dias: push/pull/pernas duas vezes. A spec pede variação na segunda
    passagem, não repetição literal."""
    _, plan = _plan(db, dias=6)
    por_foco = {s.focus: {sl.exercise_name for sl in s.slots} for s in plan.sessions}
    for a, b in (("push a", "push b"), ("pull a", "pull b"), ("pernas a", "pernas b")):
        assert not (por_foco[a] & por_foco[b]), f"{a} e {b} repetem exercício: {por_foco[a] & por_foco[b]}"


def test_acessorio_de_volume_respeita_o_teto_de_funcao(db):
    """Regressão de um bug que só aparecia com ponto fraco em músculo de pool
    magro. Posterior de coxa tem 3 flexoras na base e bíceps tem 10 roscas todas
    da mesma função; ao encher o volume desses pontos fracos, add_accessory_slot
    acrescentava um TERCEIRO exercício da mesma função e o revisor reprovava o
    treino que o próprio montador tinha acabado de montar. O teto de 2 do
    add_accessory_slot é o que faz montador e revisor concordarem.
    """
    from app.ai.methods_engine import add_accessory_slot

    spec, plan = _plan(db, dias=4, weak_points=[M.BICEPS, M.HAMSTRINGS])
    for _ in range(24):  # muito mais vagas do que qualquer volume real pediria
        for musculo in (M.BICEPS, M.HAMSTRINGS, M.QUADS, M.BACK, M.CHEST):
            add_accessory_slot(db, plan, musculo, max_per_session=9)
    assert plan_review.redundancias(plan) == []
    assert plan_review.review(plan, method=spec) == []


def test_desligar_tecnica_reverte_dicas_ativas(db):
    """Regressão relatada pelo usuário: ele respondeu "não" pra técnica avançada
    e o coach continuou gerando treino com técnica. Causa: CoachingTechniqueCue
    sobrevive a remontagens de propósito (é o que faz uma técnica aplicada
    manualmente persistir), mas nada revertia as dicas já ativas quando a
    preferência mudava — elas ficavam pra sempre, independente da escolha nova.
    """
    from sqlalchemy import delete, select

    from app.coaching import plan_service
    from app.models.coaching_technique_cue import CoachingTechniqueCue
    from app.models.routine import Routine, RoutineExercise
    from app.models.user import User
    from app.models.user_profile import UserProfile

    email = "__tmp_test_desliga_tecnica__@teste.local"

    def limpar():
        u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if u is None:
            return None
        rids = [r.id for r in db.execute(select(Routine).where(Routine.user_id == u.id)).scalars()]
        if rids:
            db.execute(delete(RoutineExercise).where(RoutineExercise.routine_id.in_(rids)))
            db.execute(delete(Routine).where(Routine.id.in_(rids)))
        db.execute(delete(CoachingTechniqueCue).where(CoachingTechniqueCue.user_id == u.id))
        db.execute(delete(UserProfile).where(UserProfile.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
        db.commit()

    limpar()
    from app.models.user import Plan
    from app.models.user_profile import (
        ActivityLevel, BiologicalSex, ExperienceLevel, Goal, TrainingLocation,
    )

    u = User(email=email, handle="__tmp_dt2__", display_name="T", password_hash="x", plan=Plan.PRO)
    db.add(u)
    db.flush()
    perfil = UserProfile(
        user_id=u.id, age=30, height_cm=180,
        biological_sex=BiologicalSex.MALE, activity_level=ActivityLevel.MODERATE,
        training_location=TrainingLocation.ACADEMIA_COMPLETA,
        experience_level=ExperienceLevel.INTERMEDIARIO, goal=Goal.HIPERTROFIA,
        training_days_per_week=4, session_length="curto",  # curto sempre prescreve técnica
        allow_advanced_techniques=True, periodization="auto",
    )
    db.add(perfil)
    db.commit()

    from app.coaching import workout_builder as wb

    try:
        r1 = wb.build_and_save(db, u)
        assert r1.get("technique_note"), "pré-condição: precisa ter criado alguma dica"
        ativas = db.execute(
            select(CoachingTechniqueCue).where(
                CoachingTechniqueCue.user_id == u.id, CoachingTechniqueCue.reverted_at.is_(None)
            )
        ).scalars().all()
        assert ativas

        plan_service.apply_answers_to_profile(db, u, {"allow_advanced_techniques": False})
        db.commit()
        ainda_ativas = db.execute(
            select(CoachingTechniqueCue).where(
                CoachingTechniqueCue.user_id == u.id, CoachingTechniqueCue.reverted_at.is_(None)
            )
        ).scalars().all()
        assert not ainda_ativas, "responder 'não' deveria reverter as dicas já ativas"

        r2 = wb.build_and_save(db, u)
        assert r2.get("technique_note") is None, "não pode montar técnica com allow_advanced_techniques=False"
    finally:
        limpar()


# --- Ponto fraco: ORDEM ---------------------------------------------------
def test_ponto_fraco_sem_composto_abre_a_sessao(db):
    """O bug principal relatado: trocar o ponto fraco não mudava o treino.

    Bíceps e tríceps não aparecem em vaga de COMPOSTO em blueprint nenhum, e a
    promoção só acontecia entre compostos — então marcar braço como ponto fraco
    não mexia uma vírgula na ordem. Agora o melhor isolador dele sobe pra
    abertura nos dias que treinam o músculo.
    """
    _, plan = _plan(db, dias=6, weak_points=[M.BICEPS])
    dias_de_biceps = [s for s in plan.sessions if any(sl.muscle_group == M.BICEPS.value for sl in s.slots)]
    assert dias_de_biceps, "pré-condição: algum dia tem que treinar bíceps"
    for s in dias_de_biceps:
        assert s.slots[0].muscle_group == M.BICEPS.value, (
            f"{s.focus} abre com {s.slots[0].exercise_name}; o ponto fraco tinha que abrir"
        )
        assert s.slots[0].priority_opener, "a abertura por prioridade precisa se declarar pro validador"


def test_abertura_por_prioridade_passa_na_coerencia(db):
    """Abrir com isolador é exceção, não buraco: o resto da regra mestra continua
    valendo no mesmo treino."""
    for fraco in (M.BICEPS, M.TRICEPS):
        spec, plan = _plan(db, dias=6, weak_points=[fraco])
        assert plan_review.review(plan, method=spec) == [], fraco


def test_dia_de_membros_abre_pelo_braco(db):
    """A divisão Torso/Limbs existe pra dar volume a músculo menor. Deixar o
    braço atrás de agachamento e terra entrega o contrário do que ela promete."""
    _, plan = _plan(db, dias=4, weak_points=[M.BICEPS])
    membros = [s for s in plan.sessions if s.focus.startswith("membros")]
    assert membros
    for s in membros:
        assert s.slots[0].muscle_group in (M.BICEPS.value, M.TRICEPS.value), (
            f"{s.focus} abre com {s.slots[0].exercise_name}, esperado um exercício de braço"
        )


# --- Variação por pessoa ---------------------------------------------------
def test_pessoas_diferentes_recebem_exercicios_diferentes(db):
    """Duas pessoas com respostas idênticas recebiam o treino idêntico, exercício
    por exercício. O treino estava certo, mas não parecia dela."""
    def nomes(seed):
        _, plan = _plan(db, dias=4, seed=seed)
        return [sl.exercise_name for s in plan.sessions for sl in s.slots]

    a, b = nomes(101), nomes(202)
    assert a != b, "o sorteio por pessoa não produziu nenhuma diferença"


def test_variacao_e_estavel_para_a_mesma_pessoa(db):
    """A variação é por PESSOA, não por montagem: remontar o treino não pode
    trocar os exercícios do nada."""
    _, p1 = _plan(db, dias=4, seed=101)
    _, p2 = _plan(db, dias=4, seed=101)
    assert [sl.exercise_name for s in p1.sessions for sl in s.slots] == [
        sl.exercise_name for s in p2.sessions for sl in s.slots
    ]


def test_variacao_nao_rebaixa_o_tier(db):
    """A variação não pode custar qualidade: ninguém pode ficar com o treino pior
    por sorteio. Vaga a vaga, o tier escolhido é o mesmo pra todo mundo."""
    def tiers(seed):
        _, plan = _plan(db, dias=4, seed=seed)
        return [
            [_tier_de(db, sl.exercise_id) for sl in s.slots]
            for s in plan.sessions
        ]

    base = tiers(None)
    for seed in (7, 42, 101, 999):
        assert tiers(seed) == base, f"a semente {seed} mudou o tier de alguma vaga"


def _tier_de(db, exercise_id: int) -> Tier:
    from app.ai.exercise_taxonomy import taxon_for_exercise

    return taxon_for_exercise(db.get(Exercise, exercise_id)).tier


def test_variacao_passa_na_coerencia(db):
    """Sortear entre equivalentes não pode quebrar a estrutura da semana."""
    for seed in (7, 42, 101, 999):
        spec, plan = _plan(db, dias=4, seed=seed)
        assert plan_review.review(plan, method=spec) == [], seed


def test_determinismo(db):
    """Mesma entrada, mesmo treino — o produto não pode sortear."""
    _, p1 = _plan(db, dias=4)
    _, p2 = _plan(db, dias=4)
    assert [[sl.exercise_id for sl in s.slots] for s in p1.sessions] == \
           [[sl.exercise_id for sl in s.slots] for s in p2.sessions]
