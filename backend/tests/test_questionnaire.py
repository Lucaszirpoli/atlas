"""O QUESTIONÁRIO — a coleta que alimenta treino e dieta.

Esta camada não tinha teste nenhum. Os testes de volume escrevem `weak_points`
direto no perfil, então a tradução "resposta da tela -> campo do perfil" nunca
foi exercitada: dava pra quebrar `apply_answers_to_profile` inteiro e a suíte
continuar verde.

O que se protege aqui é a regra do arquivo: **toda pergunta muda um número do
plano**. Um campo que a tela mostra e o perfil não guarda é uma pergunta que a
pessoa responde à toa — foi exatamente o que aconteceu com os 6 campos de texto
livre que esta reescrita removeu.
"""

from __future__ import annotations

import pytest

from app.coaching import questionnaire, training_brain, volume_landmarks
from app.models.exercise import MuscleGroup as M

TODOS_CAMPOS = [f for s in questionnaire.steps() for f in s["fields"]]
CAMPOS_POR_CHAVE = {f["key"]: f for f in TODOS_CAMPOS}


@pytest.fixture(scope="module")
def db():
    from app.core.db import SessionLocal

    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


# --- A regra do arquivo -----------------------------------------------------
def test_nenhuma_pergunta_e_de_texto_livre():
    """Texto livre o motor não consegue obedecer.

    O questionário antigo perguntava lesões num campo aberto e guardava a
    resposta num TEXT que nenhuma regra lia: quem escrevia "dor no ombro direito
    em supino reto" recebia supino reto do mesmo jeito. Se um campo de texto
    voltar aqui, é porque alguém está coletando algo que o plano vai ignorar.
    """
    abertos = [f["key"] for f in TODOS_CAMPOS if f["type"] == "text"]
    assert abertos == [], f"campos de texto livre voltaram ao questionário: {abertos}"


def test_todo_campo_tem_opcao_ou_e_numero():
    """Escolha única e múltipla precisam de opções pra tela desenhar."""
    for f in TODOS_CAMPOS:
        if f["type"] in ("single", "multi"):
            assert f.get("options"), f"{f['key']} é {f['type']} e não tem opções"


def test_campo_condicional_aponta_pra_campo_que_existe():
    """`shows_if` apontando pra chave errada esconde o campo pra sempre, em
    silêncio — a tela simplesmente nunca o mostra."""
    for f in TODOS_CAMPOS:
        cond = f.get("shows_if")
        if cond:
            assert cond["field"] in CAMPOS_POR_CHAVE, (
                f"{f['key']} depende de {cond['field']}, que não existe no questionário"
            )


def test_condicional_de_sim_ou_nao_enxerga_o_mesmo_que_a_tela():
    """A armadilha do booleano: o app compara com String(true) -> "true" e o
    Python faria str(True) -> "True". Sem normalizar, todo campo que só aparece
    quando a pessoa responde "sim" ficaria visível na tela e invisível pro
    backend."""
    campo = CAMPOS_POR_CHAVE["injury_regions"]
    assert questionnaire._visivel(campo, {"has_injury": True}) is True
    assert questionnaire._visivel(campo, {"has_injury": False}) is False
    assert questionnaire._visivel(campo, {}) is False


def test_obrigatorio_escondido_nao_bloqueia_a_conclusao():
    """Os campos de meta manual são obrigatórios, mas só quando a pessoa escolhe
    "eu defino" — quem fica no automático não pode ser barrado por eles."""
    base = {
        "goal": "hipertrofia", "biological_sex": "male", "age": 30, "height_cm": 180,
        "weight_kg": 80, "activity_level": "moderate", "calorie_goal_mode": "auto",
        "training_time": "1_3a", "training_location": "academia_completa",
        "training_days_per_week": "4", "session_length": "medio",
    }
    assert questionnaire.missing_required(base) == []
    manual = {**base, "calorie_goal_mode": "manual"}
    assert "manual_kcal" in questionnaire.missing_required(manual)


# --- A fila de prioridade ---------------------------------------------------
def test_prioridades_viram_lista_ordenada():
    respostas = {"priority_1": "chest", "priority_2": "back", "priority_3": "biceps"}
    assert questionnaire.ordered_priorities(respostas) == ["chest", "back", "biceps"]


def test_prioridade_repetida_vira_uma_so():
    """Nada impede a pessoa de marcar peito em duas vagas. Contar duas vezes
    daria a ela um 'peito duplo' que o cálculo de volume não sabe tratar."""
    respostas = {"priority_1": "chest", "priority_2": "chest", "priority_3": "back"}
    assert questionnaire.ordered_priorities(respostas) == ["chest", "back"]


def test_vaga_em_branco_e_pulada_sem_deslocar_a_ordem():
    """Deixar a 2ª em branco e preencher a 3ª não pode virar uma lista com
    buraco — quem estava em 3º passa a ser o 2º da fila."""
    respostas = {"priority_1": "chest", "priority_2": "", "priority_3": "back"}
    assert questionnaire.ordered_priorities(respostas) == ["chest", "back"]


def test_prioridades_fazem_a_volta_pra_tela():
    """Reabrir o questionário tem que mostrar a escolha que já está no perfil."""
    de_volta = questionnaire.priorities_to_answers(["chest", "back"])
    assert de_volta == {"priority_1": "chest", "priority_2": "back", "priority_3": None}


def test_teto_de_tres_prioridades():
    assert training_brain.WEAK_POINTS_MAX == 3
    assert len(questionnaire.PRIORITY_KEYS) == training_brain.WEAK_POINTS_MAX


# --- A ordem tem que MUDAR o volume ----------------------------------------
@pytest.mark.parametrize("musculo", [M.CHEST, M.BACK, M.BICEPS])
def test_posicao_na_fila_muda_o_volume(musculo):
    """Se as três prioridades recebessem o mesmo volume, a ordem seria
    decorativa: marcar peito, costas e bíceps daria o mesmo plano que marcar na
    ordem inversa. É a queixa que já existiu uma vez ("troco o ponto fraco e não
    muda nada"), agora na versão ordenada.

    Medido no FIM do mesociclo, que é onde os topos de faixa se separam — na
    semana 1 todos partem do mesmo piso, de propósito.
    """
    fim = training_brain.MESOCYCLE_WEEKS
    alvos = [
        volume_landmarks.weekly_target_sets(
            musculo, "intermediario", fim, priority=p, session_length="longo",
        )
        for p in ("alta", "alta_2", "alta_3")
    ]
    assert alvos[0] > alvos[1] > alvos[2], dict(zip(("1ª", "2ª", "3ª"), alvos))


def test_terceira_prioridade_ainda_ganha_de_quem_nao_e_prioridade():
    """O que decai é o TETO, não o piso: mesmo a 3ª da fila precisa receber mais
    que um músculo sem prioridade, senão marcá-la não teria sido uma escolha."""
    fim = training_brain.MESOCYCLE_WEEKS
    terceira = volume_landmarks.weekly_target_sets(
        M.BICEPS, "intermediario", fim, priority="alta_3", session_length="longo")
    financiador = volume_landmarks.weekly_target_sets(
        M.BICEPS, "intermediario", fim, priority="baixa", session_length="longo")
    assert terceira > financiador


def test_plano_semanal_respeita_a_ordem_recebida():
    """`weekly_plan` recebe a lista ordenada e é ela que decide o topo de cada
    um — não a ordem alfabética nem a ordem do enum."""
    fim = training_brain.MESOCYCLE_WEEKS
    musculos = [M.CHEST, M.BACK, M.BICEPS, M.QUADS]
    primeiro = volume_landmarks.weekly_plan(
        musculos, "intermediario", fim, weak_points=[M.CHEST, M.BACK, M.BICEPS],
        session_length="longo")
    invertido = volume_landmarks.weekly_plan(
        musculos, "intermediario", fim, weak_points=[M.BICEPS, M.BACK, M.CHEST],
        session_length="longo")
    assert primeiro[M.CHEST] > invertido[M.CHEST]
    assert invertido[M.BICEPS] > primeiro[M.BICEPS]


# --- Nível derivado do tempo de treino --------------------------------------
def test_nivel_sai_do_tempo_de_treino():
    """A auto-avaliação saiu do questionário: ela é inflada e o nível vale 15%
    do volume semanal. O mapa é conservador de propósito."""
    assert training_brain.experience_from_training_time("menos_6m") == "iniciante"
    assert training_brain.experience_from_training_time("1_3a") == "intermediario"
    assert training_brain.experience_from_training_time("3_5a") == "intermediario"
    assert training_brain.experience_from_training_time("mais_5a") == "avancado"


def test_tempo_de_treino_desconhecido_nao_promove_ninguem():
    """Valor que não existe devolve None, e quem chama MANTÉM o nível anterior —
    nunca promove por acidente."""
    assert training_brain.experience_from_training_time(None) is None
    assert training_brain.experience_from_training_time("qualquer_coisa") is None


def test_toda_opcao_de_tempo_mapeia_um_nivel_valido():
    """Opção na tela sem nível correspondente deixaria a pessoa sem
    experience_level — e o volume cairia no padrão silenciosamente."""
    niveis = {"iniciante", "intermediario", "avancado"}
    for valor, _, nivel in training_brain.TRAINING_TIME:
        assert nivel in niveis, f"{valor} aponta pra nível inválido: {nivel}"


# --- O fator de recuperação -------------------------------------------------
class _Perfil:
    """Um perfil mínimo — recovery_factor lê por atributo."""

    def __init__(self, **kw):
        for campo in ("sleep_quality", "stress_level", "recovery_between", "other_sport"):
            setattr(self, campo, kw.get(campo))


def test_quem_nao_respondeu_nada_fica_neutro():
    """O fator existe pra ajustar quem respondeu, nunca pra punir quem pulou."""
    assert training_brain.recovery_factor(_Perfil()) == 1.0


def test_recuperacao_ruim_reduz_e_boa_aumenta():
    ruim = training_brain.recovery_factor(_Perfil(
        sleep_quality="ruim", stress_level="alto",
        recovery_between="dolorido", other_sport="intenso"))
    boa = training_brain.recovery_factor(_Perfil(
        sleep_quality="boa", stress_level="baixo",
        recovery_between="recuperado", other_sport="nao"))
    assert ruim < 1.0 < boa


def test_fator_respeita_piso_e_teto():
    """O piso existe pra 'tudo ruim' reduzir o treino sem apagá-lo; o teto, pra
    dormir bem não virar licença pra volume ilimitado."""
    ruim = training_brain.recovery_factor(_Perfil(
        sleep_quality="ruim", stress_level="alto",
        recovery_between="dolorido", other_sport="intenso"))
    boa = training_brain.recovery_factor(_Perfil(
        sleep_quality="boa", stress_level="baixo",
        recovery_between="recuperado", other_sport="nao"))
    assert training_brain.RECOVERY_FACTOR_MIN <= ruim
    assert boa <= training_brain.RECOVERY_FACTOR_MAX


def test_recuperacao_ruim_tira_serie_do_plano():
    """O fator só vale se chegar no número de séries — é o mesmo erro do ponto
    fraco que existia no papel e não chegava no treino."""
    musculos = [M.CHEST, M.BACK, M.QUADS]
    cheio = volume_landmarks.weekly_plan(
        musculos, "intermediario", 2, session_length="medio", recovery=1.0)
    reduzido = volume_landmarks.weekly_plan(
        musculos, "intermediario", 2, session_length="medio",
        recovery=training_brain.RECOVERY_FACTOR_MIN)
    assert sum(reduzido.values()) < sum(cheio.values())


def test_toda_resposta_de_recuperacao_tem_peso_definido():
    """Uma opção na tela sem entrada no mapa de pesos seria uma pergunta que não
    muda nada — exatamente o que esta reescrita foi feita pra eliminar."""
    for campo, opcoes in (
        ("sleep_quality", training_brain.SLEEP_QUALITY_VALUES),
        ("stress_level", training_brain.STRESS_LEVEL_VALUES),
        ("recovery_between", training_brain.RECOVERY_BETWEEN_VALUES),
        ("other_sport", training_brain.OTHER_SPORT_VALUES),
    ):
        pesos = training_brain._RECOVERY_DELTA[campo]
        assert opcoes == set(pesos), f"{campo}: opções e pesos não batem"


# --- A resposta chegando no PERFIL ------------------------------------------
# É o trecho que não tinha teste nenhum: dava pra apagar
# `apply_answers_to_profile` inteiro e a suíte continuar verde, porque os outros
# testes escrevem no perfil direto.
RESPOSTAS_BASE = {
    "goal": "hipertrofia", "biological_sex": "male", "age": 30, "height_cm": 180,
    "activity_level": "moderate", "calorie_goal_mode": "auto",
    "training_time": "mais_5a", "training_location": "academia_completa",
    "training_days_per_week": "4", "session_length": "medio",
}


@pytest.fixture
def perfil(db):
    """Um usuário Pro descartável, criado e removido no mesmo teste."""
    from sqlalchemy import delete, select

    from app.models.user import Plan, User
    from app.models.user_profile import (
        ActivityLevel, BiologicalSex, ExperienceLevel, Goal, TrainingLocation, UserProfile,
    )

    email = "__tmp_quest__@teste.local"

    def limpar():
        u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if u is not None:
            db.execute(delete(UserProfile).where(UserProfile.user_id == u.id))
            db.execute(delete(User).where(User.id == u.id))
            db.commit()

    limpar()
    u = User(email=email, handle="__tmp_q__", display_name="T", password_hash="x", plan=Plan.PRO)
    db.add(u)
    db.flush()
    db.add(UserProfile(
        user_id=u.id, age=30, height_cm=180,
        biological_sex=BiologicalSex.MALE, activity_level=ActivityLevel.MODERATE,
        training_location=TrainingLocation.ACADEMIA_COMPLETA,
        experience_level=ExperienceLevel.INICIANTE, goal=Goal.HIPERTROFIA,
    ))
    db.commit()
    db.refresh(u)
    try:
        yield u
    finally:
        limpar()


def _aplicar(db, user, extras: dict):
    from app.coaching import plan_service

    plan_service.apply_answers_to_profile(db, user, {**RESPOSTAS_BASE, **extras})
    db.flush()
    return user.profile


def test_prioridades_da_tela_chegam_ordenadas_no_perfil(db, perfil):
    p = _aplicar(db, perfil, {
        "priority_1": "back", "priority_2": "chest", "priority_3": "calves"})
    assert p.weak_points == ["back", "chest", "calves"]
    assert p.weak_point == "back", "o campo legado precisa apontar pra 1ª prioridade"


def test_nivel_e_gravado_a_partir_do_tempo_de_treino(db, perfil):
    from app.models.user_profile import ExperienceLevel

    assert perfil.profile.experience_level == ExperienceLevel.INICIANTE
    p = _aplicar(db, perfil, {})  # base tem training_time="mais_5a"
    assert p.training_time == "mais_5a"
    assert p.experience_level == ExperienceLevel.AVANCADO


def test_respostas_estruturadas_sao_gravadas(db, perfil):
    """Cada uma destas substituiu um campo de texto que ninguém lia."""
    p = _aplicar(db, perfil, {
        "rir_accuracy": "nao", "failure_comfort": "evito", "load_preference": "leve",
        "gym_crowding": "cheia", "split_preference": "upper_lower",
        "limitations": ["mobilidade", "equilibrio"],
        "known_techniques": ["myo_reps"],
        "food_dislikes_list": ["figado", "jilo"],
    })
    assert p.rir_accuracy == "nao"
    assert p.failure_comfort == "evito"
    assert p.load_preference == "leve"
    assert p.gym_crowding == "cheia"
    assert p.split_preference == "upper_lower"
    assert p.limitations == ["mobilidade", "equilibrio"]
    assert p.known_techniques == ["myo_reps"]
    assert p.food_dislikes_list == ["figado", "jilo"]


def test_valor_invalido_nao_entra_no_perfil(db, perfil):
    """A tela é a fonte das opções, mas o servidor não confia nela."""
    p = _aplicar(db, perfil, {
        "gym_crowding": "lotadissima", "limitations": ["mobilidade", "inventado"]})
    assert p.gym_crowding is None
    assert p.limitations == ["mobilidade"]


def test_campo_nao_enviado_preserva_o_valor_anterior(db, perfil):
    """Avançar uma etapa sem tocar num campo não pode apagá-lo."""
    _aplicar(db, perfil, {"gym_crowding": "cheia"})
    p = _aplicar(db, perfil, {})  # sem gym_crowding nas respostas
    assert p.gym_crowding == "cheia"


def test_dizer_que_nao_tem_mais_lesao_limpa_as_regioes(db, perfil):
    """Sem isto, quem se recupera fica com exercício bloqueado pra sempre: a
    flag vira "não" e as regiões marcadas continuam filtrando o plano."""
    p = _aplicar(db, perfil, {
        "has_injury": True, "injury_regions": ["ombro"], "medical_clearance": True})
    assert p.injury_regions == ["ombro"] and p.medical_clearance is True

    p = _aplicar(db, perfil, {"has_injury": False, "injury_regions": ["ombro"]})
    assert p.has_injury is False
    assert p.injury_regions == []
    assert p.medical_clearance is None


def test_dizer_que_nao_sente_mais_dor_limpa_regiao_e_intensidade(db, perfil):
    p = _aplicar(db, perfil, {
        "has_pain": True, "pain_regions": ["joelho"], "pain_intensity": "forte"})
    assert p.pain_regions == ["joelho"] and p.pain_intensity == "forte"

    p = _aplicar(db, perfil, {"has_pain": False})
    assert p.pain_regions == []
    assert p.pain_intensity is None


# --- Quem JÁ usava o app ----------------------------------------------------
# O questionário trocou de perguntas. Quem tem plano ativo respondeu chaves que
# não existem mais e não respondeu as de agora — se a migração falhar, essa
# pessoa abre a aba Objetivo travada num campo obrigatório que ela nunca viu.
def test_quem_ja_tinha_nivel_nao_precisa_redizer_o_tempo_de_treino(db, perfil):
    """`training_time` é obrigatório e é novo. Pra perfil antigo ele nasce do
    nível que a auto-avaliação já tinha gravado."""
    from app.coaching import plan_service
    from app.models.user_profile import ExperienceLevel

    p = perfil.profile
    p.experience_level = ExperienceLevel.AVANCADO
    p.training_time = None
    db.flush()

    base = plan_service.answers_from_profile(db, perfil)
    assert base["training_time"] == "mais_5a"
    assert "training_time" not in questionnaire.missing_required(base), (
        "perfil antigo ficaria travado num obrigatório que ele nunca viu"
    )


def test_resposta_gravada_ganha_do_palpite_da_migracao(db, perfil):
    """O palpite só vale enquanto a pessoa não respondeu de verdade."""
    from app.coaching import plan_service
    from app.models.user_profile import ExperienceLevel

    p = perfil.profile
    p.experience_level = ExperienceLevel.AVANCADO
    p.training_time = "menos_6m"
    db.flush()

    assert plan_service.answers_from_profile(db, perfil)["training_time"] == "menos_6m"


def test_pontos_fracos_antigos_viram_a_fila_de_prioridade(db, perfil):
    """A lista sem ordem que já estava no perfil precisa reaparecer nas três
    vagas — senão quem priorizou peito e costas abre a tela sem prioridade
    nenhuma e o plano seguinte sai equalizado."""
    from app.coaching import plan_service

    perfil.profile.weak_points = ["back", "chest"]
    db.flush()

    base = plan_service.answers_from_profile(db, perfil)
    assert base["priority_1"] == "back"
    assert base["priority_2"] == "chest"
    assert base["priority_3"] is None
