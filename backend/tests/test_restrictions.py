"""O que sai do treino por lesão, dor, limitação e equipamento.

Estas respostas eram coletadas e não filtravam nada — o questionário perguntava
onde doía e o plano vinha igual. Aqui se protege as duas regras que governam o
filtro, e a segunda é a que pode machucar alguém se quebrar:

  1. restrição tira MOVIMENTO, nunca MÚSCULO;
  2. a biblioteca precisa SOBRAR — um filtro que esvazia a vaga não protege
     ninguém, só entrega um treino pela metade.
"""

from __future__ import annotations

import pytest

from app.ai import exercise_taxonomy as tx
from app.ai.exercise_taxonomy import Pattern, Systemic
from app.coaching import restrictions
from app.models.exercise import Equipment, MuscleGroup as M

# Os grupos que TODO treino precisa conseguir montar, aconteça o que acontecer.
ESSENCIAIS = [M.CHEST, M.BACK, M.SHOULDERS, M.BICEPS, M.TRICEPS,
              M.QUADS, M.HAMSTRINGS, M.GLUTES, M.CALVES]

# A biblioteca vem do SEED, não do banco: o filtro é decidido em Python sobre
# atributos que o seed já carrega, então dá pra testá-lo sem subir banco nenhum.
# Tupla: (nome, músculo principal, secundários, equipamento, dificuldade, imagem).
from app.scripts.seed_exercises_curated import EXERCISES  # noqa: E402

_POR_NOME = {linha[0]: linha for linha in EXERCISES}


def biblioteca():
    """(nome, taxon, músculo, equipamento) de todo exercício da tabela."""
    for nome, taxon in tx.TAXONOMY.items():
        seed = _POR_NOME.get(nome)
        if seed is None:
            continue
        yield nome, taxon, seed[1], seed[3]


def sobrevivem(perfil: restrictions.Perfil, muscle=None):
    return [
        nome for nome, taxon, mus, equip in biblioteca()
        if (muscle is None or mus == muscle)
        and not restrictions.proibido(taxon, mus, equip, perfil)
    ]


def test_a_biblioteca_do_seed_bate_com_a_taxonomia():
    """Se o seed e a taxonomia divergirem, todos os testes abaixo medem o vazio."""
    faltando = [n for n in tx.TAXONOMY if n not in _POR_NOME]
    assert not faltando, f"na taxonomia e não no seed: {faltando[:5]}"


# --- A regra que não pode quebrar -------------------------------------------
@pytest.mark.parametrize("regiao", sorted(restrictions.POR_REGIAO))
@pytest.mark.parametrize("musculo", ESSENCIAIS)
def test_nenhuma_lesao_zera_um_grupo_muscular(regiao, musculo):
    """Quem tem ombro lesionado continua treinando peito — só não recebe
    desenvolvimento. Zerar um grupo transformaria uma limitação pontual num
    buraco permanente no treino."""
    perfil = restrictions.Perfil(regioes=frozenset({regiao}))
    restantes = sobrevivem(perfil, musculo)
    assert restantes, f"lesão de {regiao} zerou {musculo.value}"


@pytest.mark.parametrize("musculo", ESSENCIAIS)
def test_nem_todas_as_limitacoes_juntas_zeram_um_grupo(musculo):
    """O pior caso possível: a pessoa marcou todas as limitações funcionais."""
    perfil = restrictions.Perfil(limitacoes=frozenset(restrictions.POR_LIMITACAO))
    assert sobrevivem(perfil, musculo), f"todas as limitações zeraram {musculo.value}"


@pytest.mark.parametrize("musculo", ESSENCIAIS)
def test_o_pior_caso_de_todos_ainda_deixa_treino_de_pe(musculo):
    """Todas as regiões e todas as limitações ao mesmo tempo. É um cenário que
    quase não acontece, e é justamente o que revelaria um filtro largo demais."""
    perfil = restrictions.Perfil(
        regioes=frozenset(restrictions.POR_REGIAO),
        limitacoes=frozenset(restrictions.POR_LIMITACAO),
    )
    assert sobrevivem(perfil, musculo), f"o pior caso zerou {musculo.value}"


# --- Cada restrição tira o que deve -----------------------------------------
def test_ombro_tira_o_que_passa_acima_da_cabeca():
    perfil = restrictions.Perfil(regioes=frozenset({"ombro"}))
    vivos = set(sobrevivem(perfil))
    assert "Desenvolvimento com barra" not in vivos
    assert "Desenvolvimento na máquina" not in vivos
    assert "Crucifixo reto com halteres" not in vivos, "carrega o ombro alongado"
    # ...e o peito continua treinável.
    assert "Chest press" in vivos
    assert "Supino reto no Smith" in vivos


def test_ombro_nao_encosta_na_perna():
    """O escopo existe pra isso: uma queixa de membro superior não pode tirar
    agachamento."""
    perfil = restrictions.Perfil(regioes=frozenset({"ombro"}))
    vivos = set(sobrevivem(perfil))
    assert "Hack squat" in vivos
    assert "Leg press 45°" in vivos


def test_lombar_tira_o_que_carrega_a_coluna():
    perfil = restrictions.Perfil(regioes=frozenset({"lombar"}))
    vivos = set(sobrevivem(perfil))
    for fora in ("Levantamento terra tradicional", "Levantamento terra romeno",
                 "Stiff com barra", "Good morning", "Remada curvada com barra",
                 "Agachamento livre"):
        assert fora not in vivos, f"{fora} deveria sair com lombar sensível"
    # E ainda dá pra treinar posterior e quadríceps.
    assert "Mesa flexora" in vivos
    assert "Cadeira flexora" in vivos
    assert "Leg press 45°" in vivos


def test_joelho_tira_unilateral_em_pe():
    perfil = restrictions.Perfil(regioes=frozenset({"joelho"}))
    vivos = set(sobrevivem(perfil))
    for fora in ("Agachamento búlgaro", "Afundo com halteres", "Passada com halteres"):
        assert fora not in vivos
    assert "Leg press 45°" in vivos


def test_equilibrio_tira_instavel_do_corpo_inteiro():
    perfil = restrictions.Perfil(limitacoes=frozenset({"equilibrio"}))
    vivos = set(sobrevivem(perfil))
    assert "Agachamento búlgaro" not in vivos
    assert "Barra fixa pronada" not in vivos
    assert "Cadeira extensora" in vivos


def test_respiracao_tira_o_que_acaba_por_falta_de_ar():
    perfil = restrictions.Perfil(limitacoes=frozenset({"respiracao"}))
    vivos = set(sobrevivem(perfil))
    assert "Agachamento livre" not in vivos, "é o exercício com limitante cardio"
    assert "Hack squat" in vivos


# --- Equipamento ------------------------------------------------------------
def test_so_com_halteres_e_banco_ainda_da_pra_treinar():
    perfil = restrictions.Perfil(
        equipamentos=frozenset({Equipment.DUMBBELL, Equipment.BODYWEIGHT})
    )
    vivos = set(sobrevivem(perfil))
    assert "Supino reto com halteres" in vivos
    assert "Chest press" not in vivos, "máquina não existe na casa dela"
    assert "Hack squat" not in vivos


def test_peso_corporal_esta_sempre_disponivel():
    """É o que garante que alguém que não marcou nada ainda receba treino."""
    perfil = restrictions.Perfil(equipamentos=frozenset(restrictions._SEMPRE_DISPONIVEL))
    assert sobrevivem(perfil), "sem equipamento nenhum não sobrou exercício"


# --- Leitura do perfil ------------------------------------------------------
class _P:
    """Perfil mínimo — restrictions.perfil_de lê por atributo."""

    def __init__(self, **kw):
        campos = ("has_injury", "injury_regions", "medical_clearance", "has_pain",
                  "pain_regions", "pain_intensity", "limitations", "home_equipment",
                  "training_location")
        for c in campos:
            setattr(self, c, kw.get(c))


class _Local:
    def __init__(self, value):
        self.value = value


def test_dor_leve_nao_filtra_nada():
    """Zerar exercício por um incômodo de 2/10 tiraria da pessoa justamente o
    movimento que a mantém treinando."""
    p = _P(has_pain=True, pain_regions=["ombro"], pain_intensity="leve")
    assert restrictions.perfil_de(p).regioes == frozenset()


@pytest.mark.parametrize("intensidade", ["moderada", "forte"])
def test_dor_relevante_filtra_como_lesao(intensidade):
    p = _P(has_pain=True, pain_regions=["ombro"], pain_intensity=intensidade)
    assert restrictions.perfil_de(p).regioes == frozenset({"ombro"})


def test_lesao_desmarcada_nao_filtra_mesmo_com_regiao_gravada():
    """A flag manda. Sem isso, quem se recupera continua com exercício
    bloqueado."""
    p = _P(has_injury=False, injury_regions=["ombro"])
    assert restrictions.perfil_de(p).regioes == frozenset()


def test_lesao_e_dor_somam_regioes():
    p = _P(has_injury=True, injury_regions=["ombro"],
           has_pain=True, pain_regions=["joelho"], pain_intensity="forte")
    assert restrictions.perfil_de(p).regioes == frozenset({"ombro", "joelho"})


def test_regiao_desconhecida_e_ignorada():
    p = _P(has_injury=True, injury_regions=["ombro", "inventado"])
    assert restrictions.perfil_de(p).regioes == frozenset({"ombro"})


def test_equipamento_so_limita_quem_treina_em_casa():
    academia = _P(training_location=_Local("academia_completa"), home_equipment=["halteres"])
    assert restrictions.perfil_de(academia).equipamentos is None

    casa = _P(training_location=_Local("casa_com_equipamento"), home_equipment=["halteres"])
    equips = restrictions.perfil_de(casa).equipamentos
    assert Equipment.DUMBBELL in equips
    assert Equipment.MACHINE not in equips


def test_perfil_vazio_nao_proibe_nada():
    assert restrictions.PERFIL_LIVRE.vazio
    for _, taxon, mus, equip in biblioteca():
        assert not restrictions.proibido(taxon, mus, equip, restrictions.PERFIL_LIVRE)


# --- Os avisos --------------------------------------------------------------
def test_dor_forte_encaminha_sem_diagnosticar():
    """Regra 8 do produto: nenhuma tela dá diagnóstico. O aviso pode dizer
    'procure alguém', nunca dizer o que a pessoa tem."""
    avisos = restrictions.avisos(
        _P(has_pain=True, pain_regions=["ombro"], pain_intensity="forte"))
    texto = " ".join(avisos).lower()
    assert "avaliação presencial" in texto
    for palavra in ("tendinite", "lesão de manguito", "hérnia", "diagnóstico", "você tem"):
        assert palavra not in texto


def test_sem_liberacao_o_aviso_explica_o_conservadorismo():
    avisos = restrictions.avisos(
        _P(has_injury=True, injury_regions=["ombro"], medical_clearance=False))
    assert any("liberação" in a for a in avisos)


def test_quem_nao_tem_restricao_nao_recebe_aviso():
    """Aviso que aparece sempre vira ruído que ninguém lê."""
    assert restrictions.avisos(_P()) == []


def test_o_aviso_diz_o_que_foi_tirado():
    avisos = restrictions.avisos(
        _P(has_injury=True, injury_regions=["ombro"], medical_clearance=True))
    assert any("ombro" in a for a in avisos), "a pessoa precisa saber por que sumiu"


# --- A prova: chega no treino salvo -----------------------------------------
@pytest.fixture(scope="module")
def db():
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models.exercise import Exercise

    s = SessionLocal()
    if s.execute(select(Exercise.id).where(Exercise.is_hidden.is_(False)).limit(1)).first() is None:
        s.close()
        pytest.skip("biblioteca de exercícios não semeada neste banco")
    yield s
    s.close()


def _montar(db, **campos_perfil):
    """Monta um treino de verdade e devolve os nomes dos exercícios salvos."""
    from sqlalchemy import delete, select

    from app.coaching import workout_builder
    from app.models.coaching_technique_cue import CoachingTechniqueCue
    from app.models.exercise import Exercise
    from app.models.routine import Routine, RoutineExercise
    from app.models.user import Plan, User
    from app.models.user_profile import (
        ActivityLevel, BiologicalSex, ExperienceLevel, Goal, TrainingLocation, UserProfile,
    )

    email = "__tmp_restr__@teste.local"

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
    try:
        u = User(email=email, handle="__tmp_r__", display_name="T",
                 password_hash="x", plan=Plan.PRO)
        db.add(u)
        db.flush()
        db.add(UserProfile(
            user_id=u.id, age=30, height_cm=180,
            biological_sex=BiologicalSex.MALE, activity_level=ActivityLevel.MODERATE,
            training_location=TrainingLocation.ACADEMIA_COMPLETA,
            experience_level=ExperienceLevel.INTERMEDIARIO, goal=Goal.HIPERTROFIA,
            training_days_per_week=4, session_length="longo",
            allow_advanced_techniques=False, periodization="auto", wants_cardio=False,
            **campos_perfil,
        ))
        db.commit()
        db.refresh(u)

        resumo = workout_builder.build_and_save(db, u)
        nomes = [
            n for (n,) in db.execute(
                select(Exercise.name)
                .join(RoutineExercise, RoutineExercise.exercise_id == Exercise.id)
                .join(Routine, Routine.id == RoutineExercise.routine_id)
                .where(Routine.user_id == u.id)
            ).all()
        ]
        return resumo, nomes
    finally:
        limpar()


def test_lesao_de_ombro_tira_desenvolvimento_do_treino_salvo(db):
    """A prova de ponta a ponta: a resposta do questionário chega na rotina."""
    resumo, nomes = _montar(
        db, has_injury=True, injury_regions=["ombro"], medical_clearance=True)
    assert nomes, "não montou treino nenhum"
    for nome in nomes:
        taxon = tx.TAXONOMY.get(nome)
        if taxon is None:
            continue
        assert taxon.pattern is not Pattern.PUSH_V, (
            f"{nome} passa acima da cabeça e entrou mesmo com ombro lesionado"
        )
    assert resumo["restriction_notes"], "o treino mudou e a pessoa não foi avisada"


def test_lombar_sensivel_tira_carga_axial_do_treino_salvo(db):
    _, nomes = _montar(db, has_pain=True, pain_regions=["lombar"], pain_intensity="moderada")
    assert nomes
    for nome in nomes:
        taxon = tx.TAXONOMY.get(nome)
        if taxon is None:
            continue
        assert taxon.systemic is not Systemic.ALTO, f"{nome} carrega a coluna"


def test_com_restricao_o_treino_continua_completo(db):
    """O risco real do filtro: proteger a pessoa entregando meio treino."""
    _, com = _montar(db, has_injury=True, injury_regions=["ombro"], medical_clearance=True)
    _, sem = _montar(db)
    assert len(com) >= len(sem) * 0.7, (
        f"o filtro derrubou o treino de {len(sem)} pra {len(com)} exercícios"
    )
