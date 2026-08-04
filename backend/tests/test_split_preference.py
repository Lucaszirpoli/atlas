"""A divisão de treino que a pessoa escolhe — e quando o coach recusa.

"Não gosto de treino com superior e inferior junto" é um pedido legítimo que
não tinha para onde ir: a divisão saía só do número de dias, `split_preference`
era um campo morto no perfil, e o chat respondia "atualizei sua rotina" sem
atualizar nada.

As faixas de dias em `SPLIT_DAY_RANGE` não são opinião: saíram de montar o plano
de verdade em cada combinação e medir cobertura por grupo e equilíbrio
empurrar × puxar. O que este arquivo protege é que a preferência (a) mande
quando cabe, (b) seja RECUSADA COM EXPLICAÇÃO quando não cabe — e nunca (c)
seja engolida em silêncio, que era o comportamento antigo.
"""

from __future__ import annotations

import pytest

from app.ai import methods
from app.coaching import plan_service, questionnaire, training_brain

TODAS = ["full_body", "upper_lower", "push_pull_legs"]
DIAS = list(range(training_brain.TRAINING_DAYS_MIN, training_brain.TRAINING_DAYS_MAX + 1))


@pytest.mark.parametrize("dias", DIAS)
def test_sem_preferencia_nada_muda(dias):
    """`auto` e vazio precisam devolver exatamente o split de sempre."""
    base = methods.coach_split_for(dias)
    assert methods.coach_split_for(dias, None, "auto") == base
    assert methods.coach_split_for(dias, None, None) == base
    assert methods.coach_split_for(dias, None, "divisao_inventada") == base


@pytest.mark.parametrize("pref", TODAS)
@pytest.mark.parametrize("dias", DIAS)
def test_split_tem_um_treino_por_dia(pref, dias):
    split = methods.coach_split_for(dias, None, pref)
    assert len(split) == dias


@pytest.mark.parametrize("pref", TODAS)
@pytest.mark.parametrize("dias", DIAS)
def test_todo_foco_gerado_tem_blueprint(pref, dias):
    """Um rótulo de foco sem blueprint cairia no full body A silenciosamente —
    a pessoa pediria PPL e receberia outra coisa sem aviso."""
    from app.ai import session_blueprints as bp

    for foco in methods.coach_split_for(dias, None, pref):
        assert foco in bp.BLUEPRINTS, f"{pref}/{dias}d gerou foco desconhecido: {foco}"


@pytest.mark.parametrize("pref", TODAS)
@pytest.mark.parametrize("dias", DIAS)
def test_ou_a_preferencia_e_atendida_ou_ha_uma_explicacao(pref, dias):
    """A regra central: nunca existe o caso 'não apliquei e não falei nada'."""
    coube = methods.split_preference_fits(pref, dias)
    aviso = methods.split_preference_note(pref, dias)
    assert coube != bool(aviso), f"{pref} em {dias}d: coube={coube}, aviso={aviso!r}"
    if aviso:
        # A explicação precisa ser útil: dizer o número de dias que resolve.
        assert str(methods.SPLIT_DAY_RANGE[pref][0]) in aviso or str(
            methods.SPLIT_DAY_RANGE[pref][1]
        ) in aviso


def test_a_preferencia_atendida_realmente_troca_o_desenho_da_semana():
    """Com 6 dias, o automático é PPL. Pedir superior/inferior tem que sair
    diferente — senão a preferência é enfeite."""
    auto = methods.coach_split_for(6)
    ul = methods.coach_split_for(6, None, "upper_lower")
    assert ul != auto
    assert all("superior" in f or "inferior" in f for f in ul)


def test_corpo_inteiro_nao_e_aplicado_em_frequencia_alta():
    """Medido: em 4+ dias, corpo inteiro derruba bíceps/glúteo abaixo de 2 vagas
    por semana e desequilibra empurrar × puxar. A preferência não pode piorar o
    treino de quem a escolheu."""
    for dias in (4, 5, 6):
        assert not methods.split_preference_fits("full_body", dias)
        assert methods.coach_split_for(dias, None, "full_body") == methods.coach_split_for(dias)


def test_ppl_so_com_seis_dias():
    for dias in (2, 3, 4, 5):
        assert not methods.split_preference_fits("push_pull_legs", dias)
    assert methods.split_preference_fits("push_pull_legs", 6)


def test_preferencia_vence_o_torso_limbs():
    """Torso/Limbs é uma troca AUTOMÁTICA (4 dias + ponto fraco em músculo
    menor). Uma escolha explícita da pessoa tem que passar na frente dela."""
    auto = methods.coach_split_for(4, ["biceps"])
    assert auto == methods.TORSO_LIMBS_SPLIT
    escolhido = methods.coach_split_for(4, ["biceps"], "upper_lower")
    assert escolhido != auto


# --- Integração com o questionário e o plano --------------------------------

def test_a_pergunta_existe_na_tela():
    """Se a preferência só pudesse ser mudada pelo chat, ela seria um ajuste
    secreto — a tela é a fonte da verdade do questionário."""
    campos = {f["key"] for s in questionnaire.steps() for f in s["fields"]}
    assert "split_preference" in campos


def test_toda_opcao_da_tela_diz_de_quantos_dias_precisa():
    campo = next(
        f for s in questionnaire.steps() for f in s["fields"] if f["key"] == "split_preference"
    )
    valores = {o["value"] for o in campo["options"]}
    assert valores == training_brain.SPLIT_PREFERENCE_VALUES
    for opcao in campo["options"]:
        if opcao["value"] == "auto":
            continue
        assert "dias por semana" in opcao.get("desc", ""), opcao


def test_mudar_a_divisao_marca_o_treino_pra_ser_refeito():
    """Sem isto o plano ganharia versão nova e continuaria com o treino velho —
    o mesmo tipo de falha silenciosa que já mordeu antes."""
    mudanca = plan_service.diff_answers(
        {"split_preference": "auto"}, {"split_preference": "upper_lower"}
    )
    assert mudanca, "o diff não enxergou a mudança de divisão"
    assert "treino" in plan_service.impacted_components(mudanca)


def test_splits_possiveis_bate_com_o_que_o_motor_aceita():
    for dias in DIAS:
        possiveis = methods.splits_possible_for(dias)
        assert all(methods.split_preference_fits(p, dias) for p in possiveis)
        assert all(
            p in possiveis for p in TODAS if methods.split_preference_fits(p, dias)
        )
