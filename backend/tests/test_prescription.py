"""A PRESCRIÇÃO de cada exercício: faixa de repetições, RIR-alvo e descanso.

Antes disto o coach usava 8-12 repetições pra tudo e um descanso por objetivo —
agachamento livre e elevação lateral recebiam a mesma prescrição. Estes testes
existem pra que isso não volte por acidente: quase toda regressão possível aqui
some numa média e não aparece em teste de "o treino foi montado".

A primeira classe é a mais importante: o Cap. XI Parte H do manual NOMEIA a
faixa de alguns exercícios. Se a derivação parar de bater com eles, ela deixou
de ser uma implementação do manual e virou outra coisa.
"""

from __future__ import annotations

import re

import pytest

from app.ai import exercise_taxonomy as tx
from app.ai.exercise_taxonomy import (
    JointRisk,
    Limiter,
    Pattern,
    Resistance,
    Stability,
    Systemic,
    Taxon,
    Tier,
)
from app.coaching import prescription, training_brain


def taxon(**kw) -> Taxon:
    """Um exercício sintético: máquina isoladora comum, com o que o teste mudar."""
    base = dict(
        tier=Tier.S, pattern=Pattern.ISO, region="teste",
        stability=Stability.ALTA, resistance=Resistance.MEIO,
    )
    return Taxon(**{**base, **kw})


def faixa(nome: str) -> str:
    lo, hi = prescription.rep_band(tx.TAXONOMY[nome])
    return f"{lo}-{hi}"


# --- O manual nomeia estes (Cap. XI Parte H) --------------------------------
@pytest.mark.parametrize(
    "nome,esperado",
    [
        # "Elevação lateral: utilizar predominantemente 10-15 repetições."
        ("Elevação lateral na máquina", "10-15"),
        ("Elevação lateral com halteres", "10-15"),
        # "Crucifixo: utilizar predominantemente 8-12."
        ("Crucifixo reto com halteres", "8-12"),
        ("Crucifixo inclinado com halteres", "8-12"),
        # "Extensora: utilizar predominantemente 8-12."
        ("Cadeira extensora", "8-12"),
        # "Roscas e extensões de tríceps: 8-12 como referência geral."
        ("Rosca direta com barra W", "8-12"),
        ("Rosca na polia", "8-12"),
        ("Tríceps corda", "8-12"),
        ("Tríceps máquina", "8-12"),
        # "Panturrilhas: 8-12 como referência geral."
        ("Panturrilha em pé", "8-12"),
        ("Panturrilha sentada", "8-12"),
    ],
)
def test_faixa_bate_com_a_referencia_do_manual(nome, esperado):
    assert faixa(nome) == esperado


def test_nenhum_exercicio_passa_de_15_repeticoes():
    """Regra dura do manual: "a engine não deve utilizar faixas superiores a 15
    repetições". Vale pra biblioteca inteira e pra toda preferência de carga."""
    for nome, t in tx.TAXONOMY.items():
        for pref in (None, "pesado", "moderado", "leve", "indiferente"):
            _, hi = prescription.rep_band(t, load_preference=pref)
            assert hi <= 15, f"{nome} com preferência {pref} passou de 15 reps"


def test_nenhuma_faixa_e_invertida_ou_vazia():
    for lo, hi in prescription.REP_BANDS:
        assert 0 < lo < hi


# --- As regras de faixa, uma a uma -----------------------------------------
def test_composto_trabalha_mais_pesado_que_isolador():
    composto = prescription.rep_band(taxon(pattern=Pattern.PUSH_H))
    isolador = prescription.rep_band(taxon(pattern=Pattern.ISO))
    assert composto[0] < isolador[0]


def test_pico_na_contracao_sobe_a_faixa():
    """Pico na contração vem com carga absoluta baixa e alavanca longa: insistir
    em carga alta ali compra impulso, não estímulo."""
    encurtado = prescription.rep_band(taxon(resistance=Resistance.ENCURTADO))
    meio = prescription.rep_band(taxon(resistance=Resistance.MEIO))
    assert encurtado[0] > meio[0]


def test_risco_articular_alto_sobe_a_faixa():
    """É como o manual manda reduzir carga absoluta sem perder tensão."""
    arriscado = prescription.rep_band(taxon(joint_risk=JointRisk.ALTO))
    normal = prescription.rep_band(taxon(joint_risk=JointRisk.BAIXO))
    assert arriscado[0] > normal[0]


@pytest.mark.parametrize("limitante", [Limiter.LOMBAR, Limiter.CARDIO])
def test_lombar_e_folego_encurtam_a_serie(limitante):
    """Série que acaba pela lombar ou pelo fôlego não melhora ficando mais
    longa — o manual manda encurtar, não alongar."""
    curto = prescription.rep_band(taxon(pattern=Pattern.HIP, limiter=limitante))
    normal = prescription.rep_band(taxon(pattern=Pattern.HIP))
    assert curto[0] < normal[0]


@pytest.mark.parametrize("limitante", [Limiter.PEGADA, Limiter.ESTABILIZADORES])
def test_pegada_e_equilibrio_nao_mexem_na_faixa(limitante):
    """Encurtar a série não resolve pegada nem equilíbrio: o manual trata os dois
    com suporte e RIR, não com faixa. Só o RIR deve reagir."""
    t = taxon(pattern=Pattern.PULL_V, limiter=limitante)
    assert prescription.rep_band(t) == prescription.rep_band(taxon(pattern=Pattern.PULL_V))
    assert prescription.target_rir(t) > prescription.target_rir(taxon(pattern=Pattern.PULL_V))


def test_preferencia_da_pessoa_desloca_um_degrau_so():
    """É a única entrada subjetiva. Ela ajusta, não manda."""
    t = taxon(pattern=Pattern.PUSH_H)
    pesado = prescription.rep_band(t, load_preference="pesado")
    neutro = prescription.rep_band(t)
    leve = prescription.rep_band(t, load_preference="leve")
    assert pesado[0] < neutro[0] < leve[0]
    assert prescription.REP_BANDS.index(pesado) == prescription.REP_BANDS.index(neutro) - 1
    assert prescription.REP_BANDS.index(leve) == prescription.REP_BANDS.index(neutro) + 1


def test_preferencia_desconhecida_nao_muda_nada():
    t = taxon()
    assert prescription.rep_band(t, load_preference="indiferente") == prescription.rep_band(t)
    assert prescription.rep_band(t, load_preference="qualquer") == prescription.rep_band(t)


# --- RIR (Cap. XII) ---------------------------------------------------------
def test_maquina_estavel_pode_chegar_perto_da_falha():
    """"Máquinas altamente estáveis: RIR 1-2 nas séries iniciais, RIR 0-1 em
    séries estrategicamente selecionadas.""" ""
    t = taxon()
    assert prescription.target_rir(t) == 1
    assert prescription.target_rir(t, is_last_set=True) == 0


def test_exercicio_instavel_nunca_vai_a_falha():
    """"Evitar RIR 0 de maneira rotineira" em exercício livre de alto risco. O
    piso de segurança vale até na última série e até pra quem gosta do limite."""
    t = taxon(pattern=Pattern.KNEE, stability=Stability.BAIXA, systemic=Systemic.ALTO)
    assert prescription.target_rir(t, is_last_set=True) >= 2
    assert prescription.target_rir(t, is_last_set=True, failure_comfort="sim") >= 2


def test_ultima_serie_chega_mais_perto_da_falha():
    """"Séries iniciais podem utilizar maior RIR; séries finais podem se
    aproximar mais da falha" — não é o mesmo RIR nas três."""
    t = taxon()
    assert prescription.target_rir(t, is_last_set=True) < prescription.target_rir(t)


def test_quem_nao_sabe_estimar_rir_recebe_mais_margem():
    """"A precisão do RIR deve ser construída e validada, não presumida.""" ""
    t = taxon()
    assert prescription.target_rir(t, rir_accuracy="nao") > prescription.target_rir(t, rir_accuracy="sim")


def test_iniciante_recebe_mais_margem_que_intermediario():
    t = taxon()
    assert (
        prescription.target_rir(t, experience="iniciante")
        > prescription.target_rir(t, experience="intermediario")
    )


def test_conforto_com_a_falha_move_o_alvo_nos_dois_sentidos():
    t = taxon()
    assert (
        prescription.target_rir(t, failure_comfort="evito")
        > prescription.target_rir(t, failure_comfort="as_vezes")
        > prescription.target_rir(t, failure_comfort="sim")
    )


def test_nenhum_exercicio_arriscado_da_biblioteca_inteira_vai_a_falha():
    """Auditoria do Cap. XVIII sobre a biblioteca real (não uma amostra
    sintética): "evitar RIR 0 de maneira rotineira" pra exercício livre de alto
    risco (Cap. XII Parte C) tem que valer pros 119 exercícios, em QUALQUER
    combinação de respostas — inclusive a mais agressiva (avançado, gosta da
    falha, última série). Se algum exercício de estabilidade baixa ou custo
    sistêmico alto algum dia chegar em RIR < 2 aqui, o piso de segurança
    (`_RIR_FLOOR_ARRISCADO`) quebrou e isto pega antes de virar prescrição
    real."""
    arriscados = [
        (nome, t) for nome, t in tx.TAXONOMY.items()
        if t.stability is Stability.BAIXA or t.systemic is Systemic.ALTO
    ]
    assert len(arriscados) >= 10, "poucos exercícios de risco na amostra — o teste não estaria testando nada"
    for nome, t in arriscados:
        pior_caso = prescription.target_rir(
            t, experience="avancado", rir_accuracy="sim", failure_comfort="sim", is_last_set=True,
        )
        assert pior_caso >= 2, f"{nome} (risco) chegaria a RIR {pior_caso} na combinação mais agressiva"


def test_rir_fica_sempre_dentro_da_escala():
    """Nenhuma combinação de respostas pode produzir RIR negativo ou absurdo."""
    for t in tx.TAXONOMY.values():
        for exp in ("iniciante", "intermediario", "avancado", None):
            for acc in ("sim", "mais_ou_menos", "nao", None):
                for conf in ("evito", "as_vezes", "sim", None):
                    for ultima in (True, False):
                        r = prescription.target_rir(
                            t, experience=exp, rir_accuracy=acc,
                            failure_comfort=conf, is_last_set=ultima,
                        )
                        assert prescription.RIR_MIN <= r <= prescription.RIR_MAX


# --- Descanso (Cap. XV) -----------------------------------------------------
def test_descanso_sobe_com_o_custo_do_exercicio():
    pesado = prescription.rest_seconds(taxon(pattern=Pattern.KNEE, systemic=Systemic.ALTO))
    guiado = prescription.rest_seconds(taxon(pattern=Pattern.KNEE, systemic=Systemic.BAIXO))
    isolador = prescription.rest_seconds(taxon(pattern=Pattern.ISO))
    menor = prescription.rest_seconds(taxon(pattern=Pattern.CALF))
    assert pesado > guiado > isolador > menor


def test_emagrecer_nao_encurta_mais_o_descanso():
    """MUDANÇA DE COMPORTAMENTO, e proposital. O descanso vinha do objetivo
    (60-90s pra emagrecimento), e o manual proíbe: "nunca reduza o descanso
    apenas para aumentar desconforto". Quem encurta o intervalo troca carga por
    ofego e perde músculo justamente no déficit."""
    t = taxon(pattern=Pattern.PUSH_H, systemic=Systemic.MEDIO)
    assert prescription.rest_seconds(t, goal="emagrecimento") == prescription.rest_seconds(
        t, goal="hipertrofia"
    )


def test_performance_ganha_mais_recuperacao():
    t = taxon(pattern=Pattern.PUSH_H)
    assert prescription.rest_seconds(t, goal="performance") > prescription.rest_seconds(
        t, goal="hipertrofia"
    )


def test_condicionamento_baixo_ganha_mais_descanso():
    """Quem declarou que cansa rápido entre as séries precisa do fôlego de volta,
    senão a próxima série termina pelo cardiovascular e não pelo músculo."""
    t = taxon(pattern=Pattern.PUSH_H)
    assert prescription.rest_seconds(t, limitations=["condicionamento"]) > prescription.rest_seconds(t)


def test_serie_que_acaba_por_falta_de_ar_descansa_mais():
    assert prescription.rest_seconds(taxon(pattern=Pattern.KNEE, limiter=Limiter.CARDIO)) > (
        prescription.rest_seconds(taxon(pattern=Pattern.KNEE))
    )


def test_descanso_fica_sempre_num_intervalo_praticavel():
    for t in tx.TAXONOMY.values():
        for goal in ("hipertrofia", "emagrecimento", "performance", None):
            d = prescription.rest_seconds(t, goal=goal, limitations=["condicionamento"])
            assert prescription.REST_MIN <= d <= prescription.REST_MAX


# --- A taxonomia como um todo ----------------------------------------------
def test_todo_exercicio_da_biblioteca_tem_mecanica_declarada():
    """Estabilidade e resistência não têm padrão de propósito — exercício novo
    sem elas nem importa. Este teste é a rede pra caso alguém adicione um padrão."""
    for nome, t in tx.TAXONOMY.items():
        assert isinstance(t.stability, Stability), nome
        assert isinstance(t.resistance, Resistance), nome
        assert isinstance(t.systemic, Systemic), nome
        assert isinstance(t.joint_risk, JointRisk), nome
        assert isinstance(t.limiter, Limiter), nome


def test_exercicio_desconhecido_recebe_prescricao_conservadora():
    """Exercício custom não pode receber a prescrição agressiva que só faz
    sentido pra quem a gente sabe que é guiado e seguro."""
    from app.models.exercise import MuscleGroup

    t = tx.taxon_for("Exercício que eu inventei agora", MuscleGroup.CHEST, True)
    assert t.stability is Stability.MEDIA
    assert prescription.target_rir(t, is_last_set=True) >= 1


def test_isolador_nunca_descansa_mais_que_composto_pesado():
    """Sanidade na biblioteca inteira: se um isolador pedisse mais descanso que
    um agachamento, alguma regra inverteu."""
    pesados = [t for t in tx.TAXONOMY.values() if t.is_compound and t.systemic is Systemic.ALTO]
    isoladores = [t for t in tx.TAXONOMY.values() if not t.is_compound]
    assert min(prescription.rest_seconds(t) for t in pesados) >= max(
        prescription.rest_seconds(t) for t in isoladores
    )


# --- A prova que importa: isso CHEGA na rotina salva ------------------------
# Este projeto já foi mordido por exatamente este erro: a priorização de ponto
# fraco existia em `weekly_plan` e não chegava no treino, porque duas coisas a
# desfaziam no caminho. Uma prescrição perfeita que o montador ignora não vale
# nada, então aqui se mede o que foi GRAVADO no banco.
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


@pytest.fixture
def rotinas(db):
    """Monta um treino de verdade e devolve (nome do exercício, reps, descanso)."""
    from sqlalchemy import delete, select

    from app.coaching import workout_builder
    from app.models.coaching_technique_cue import CoachingTechniqueCue
    from app.models.exercise import Exercise
    from app.models.routine import Routine, RoutineExercise
    from app.models.user import Plan, User
    from app.models.user_profile import (
        ActivityLevel, BiologicalSex, ExperienceLevel, Goal, TrainingLocation, UserProfile,
    )

    email = "__tmp_presc__@teste.local"

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
    u = User(email=email, handle="__tmp_p__", display_name="T", password_hash="x", plan=Plan.PRO)
    db.add(u)
    db.flush()
    db.add(UserProfile(
        user_id=u.id, age=30, height_cm=180,
        biological_sex=BiologicalSex.MALE, activity_level=ActivityLevel.MODERATE,
        training_location=TrainingLocation.ACADEMIA_COMPLETA,
        experience_level=ExperienceLevel.INTERMEDIARIO, goal=Goal.HIPERTROFIA,
        training_days_per_week=4, session_length="longo",
        allow_advanced_techniques=False, periodization="auto",
    ))
    db.commit()
    db.refresh(u)

    workout_builder.build_and_save(db, u)
    linhas = list(db.execute(
        select(Exercise.name, RoutineExercise.target_reps_min, RoutineExercise.target_reps_max,
               RoutineExercise.rest_seconds)
        .join(RoutineExercise, RoutineExercise.exercise_id == Exercise.id)
        .join(Routine, Routine.id == RoutineExercise.routine_id)
        .where(Routine.user_id == u.id)
    ).all())
    try:
        yield linhas
    finally:
        limpar()


def test_treino_salvo_nao_usa_a_mesma_faixa_pra_tudo(rotinas):
    """A regressão que este trabalho existe pra corrigir: 8-12 em tudo, do
    agachamento à elevação lateral."""
    assert rotinas, "nenhum exercício foi montado"
    faixas = {(lo, hi) for _, lo, hi, _ in rotinas}
    assert len(faixas) > 1, f"todo exercício saiu com a mesma faixa: {faixas}"


def test_treino_salvo_nao_usa_o_mesmo_descanso_pra_tudo(rotinas):
    descansos = {d for *_, d in rotinas}
    assert len(descansos) > 1, f"todo exercício saiu com o mesmo descanso: {descansos}"


def test_a_duracao_estimada_bate_com_o_rotulo_escolhido(db):
    """O rótulo do tempo de sessão prometia quase o DOBRO do que o treino
    entrega ("Longo — 100–120 min" saía em 41–70). Ele foi corrigido pra ordem de
    grandeza medida; este teste existe pra ele não voltar a divergir em silêncio
    quando alguém mexer em descanso, número de exercícios ou volume.

    A tolerância é larga de propósito: a duração varia MUITO com a frequência
    (mesmo volume dividido em mais dias = treino mais curto), e o número exato de
    cada pessoa sai em `duration_note`. O que se protege aqui é a ordem de
    grandeza e a ORDEM entre os três tempos.
    """
    from sqlalchemy import delete, select

    from app.coaching import training_brain, workout_builder
    from app.models.coaching_technique_cue import CoachingTechniqueCue
    from app.models.routine import Routine, RoutineExercise
    from app.models.user import Plan, User
    from app.models.user_profile import (
        ActivityLevel, BiologicalSex, ExperienceLevel, Goal, TrainingLocation, UserProfile,
    )

    email = "__tmp_dur__@teste.local"

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

    medias = {}
    for tempo in ("curto", "medio", "longo"):
        limpar()
        u = User(email=email, handle="__tmp_du__", display_name="T",
                 password_hash="x", plan=Plan.PRO)
        db.add(u)
        db.flush()
        db.add(UserProfile(
            user_id=u.id, age=30, height_cm=180,
            biological_sex=BiologicalSex.MALE, activity_level=ActivityLevel.MODERATE,
            training_location=TrainingLocation.ACADEMIA_COMPLETA,
            experience_level=ExperienceLevel.INTERMEDIARIO, goal=Goal.HIPERTROFIA,
            training_days_per_week=3, session_length=tempo,
            allow_advanced_techniques=False, periodization="auto",
        ))
        db.commit()
        db.refresh(u)
        resumo = workout_builder.build_and_save(db, u)
        mins = resumo["estimated_minutes"]
        assert mins, f"{tempo}: nenhuma duração estimada"
        assert resumo["duration_note"], "a pessoa precisa saber quanto o treino leva"
        medias[tempo] = sum(mins) / len(mins)
    limpar()

    assert medias["curto"] < medias["medio"] < medias["longo"], (
        f"escolher mais tempo deveria dar treino mais longo: {medias}"
    )
    # O rótulo declara uma faixa ("30–45 min", "60+ min"...); o real não pode
    # passar do dobro do teto nem ficar abaixo da metade do piso — aí deixou
    # de ser ordem de grandeza.
    def _faixa_minutos(txt: str) -> tuple[int, int]:
        nums = [int(n) for n in re.findall(r"\d+", txt)]
        return nums[0], nums[-1]

    declarado = {v: _faixa_minutos(txt) for v, _, txt, _ in training_brain.SESSION_LENGTHS}
    for tempo, real in medias.items():
        lo, hi = declarado[tempo]
        assert lo / 2 <= real <= hi * 2, (
            f"{tempo}: rótulo diz {lo}–{hi} min e o treino sai com {real:.0f} min"
        )


def test_o_que_foi_gravado_bate_com_a_prescricao(rotinas):
    """Não basta variar — tem que variar do jeito certo. Compara linha a linha o
    que está no banco com o que a prescrição manda pra aquele exercício."""
    for nome, lo, hi, descanso in rotinas:
        t = tx.TAXONOMY.get(nome)
        if t is None:
            continue  # exercício fora da tabela usa o palpite, não o esperado aqui
        assert (lo, hi) == prescription.rep_band(t), f"{nome}: faixa gravada diverge"
        assert descanso == prescription.rest_seconds(t, goal="hipertrofia"), (
            f"{nome}: descanso gravado diverge"
        )


# --- Cap. XVII: auditoria da técnica antes de aplicar ----------------------
def _tx(nome):
    from app.ai.exercise_taxonomy import TAXONOMY

    return TAXONOMY[nome]


@pytest.mark.parametrize("tecnica", sorted(training_brain.TECNICAS_DE_INTENSIFICACAO))
@pytest.mark.parametrize(
    "exercicio",
    ("Agachamento livre", "Levantamento terra tradicional", "Stiff com barra",
     "Agachamento búlgaro"),
)
def test_intensificacao_e_rejeitada_em_livre_pesado(exercicio, tecnica):
    """Cap. XVII Parte C: técnica de intensificação deve ser evitada em
    "exercícios livres pesados, com grande carga axial, em que uma repetição
    falhada represente risco".

    Antes o motor escolhia a técnica por período/tempo/ponto fraco e aplicava sem
    nunca perguntar se o exercício aguentava — rest-pause em agachamento livre
    passava direto."""
    motivo = training_brain.technique_audit(_tx(exercicio), tecnica)
    assert motivo, f"{tecnica} deveria ser rejeitada em {exercicio}"
    assert len(motivo) > 20, "a rejeição tem que explicar o porquê, não só negar"


@pytest.mark.parametrize("tecnica", sorted(training_brain.TECNICAS_DE_INTENSIFICACAO))
@pytest.mark.parametrize("exercicio", ("Cadeira extensora", "Rosca Scott na máquina"))
def test_intensificacao_e_autorizada_em_maquina_estavel(exercicio, tecnica):
    """"Priorizar em máquinas, cabos, exercícios guiados, com apoio, altamente
    estáveis, com interrupção segura." A auditoria não pode ser tão dura que
    esvazie a técnica — ela existe pra separar, não pra proibir."""
    assert training_brain.technique_audit(_tx(exercicio), tecnica) is None


@pytest.mark.parametrize(
    "exercicio",
    ("Agachamento livre", "Levantamento terra tradicional", "Cadeira extensora"),
)
def test_back_off_passa_em_qualquer_exercicio(exercicio):
    """Back-off é organização de CARGA, não intensificação: "pode ser utilizado
    em exercícios compostos livres [...] a aplicação depende da segurança e da
    competência técnica, não apenas da categoria do exercício". É ele que sobra
    quando a intensificação é barrada."""
    assert training_brain.technique_audit(_tx(exercicio), "back_off") is None
