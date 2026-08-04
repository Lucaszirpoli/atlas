"""O que a pessoa marcou que NÃO come precisa sumir do cardápio — e a refeição
precisa continuar sendo uma refeição.

Os dois bugs que originaram este arquivo:

  1. quem marcava "não como whey protein" recebia whey no café da manhã. A
     causa: o questionário guarda isso em `food_dislikes_list`, e só
     `dietary_restrictions` chegava ao motor. Vocabulário partido no meio do
     caminho.
  2. almoço e jantar vinham com 6 itens (dois vegetais de meia porção, dois
     carboidratos de meia porção), e café da manhã e lanche da tarde eram
     cópias idênticas um do outro.

Nada aqui precisa de banco: o catálogo é uma tabela em Python e a distribuição
é uma função pura sobre alimentos já resolvidos.
"""

from __future__ import annotations

import itertools

import pytest

from app.ai import diet_engine as de
from app.data import food_roles as fr
from app.coaching.questionnaire import FOOD_DISLIKES, RESTRICOES

TODOS_OS_GRUPOS = {
    "PROTEIN_BOOSTERS": fr.PROTEIN_BOOSTERS,
    "WHOLE_PROTEINS": fr.WHOLE_PROTEINS,
    "MAIN_CARBS": fr.MAIN_CARBS,
    "FATS": fr.FATS,
    "VEGGIES": fr.VEGGIES,
    "FRUITS": fr.FRUITS,
    "DAIRY": fr.DAIRY,
}

# Marcar TUDO de uma vez é o pior caso possível — se o cardápio sobrevive a
# isto, sobrevive a qualquer combinação real.
TUDO = [v for v, _ in FOOD_DISLIKES] + [v for v, _ in RESTRICOES]


def test_todo_valor_do_questionario_e_reconhecido_ou_declarado():
    """Nenhum token pode cair no limbo: ou o motor sabe filtrar, ou ele está na
    lista de "não sei fazer isso" e a pessoa é avisada. O que não estivesse em
    nenhuma das duas viraria silêncio — a marca virava enfeite na tela."""
    for valor, rotulo in FOOD_DISLIKES + RESTRICOES:
        assert (
            valor in fr.KNOWN_TOKENS or valor in fr.UNSUPPORTED_TOKENS
        ), f"'{valor}' ({rotulo}) não filtra nada e nem avisa que não filtra"


def test_sem_whey_tira_o_whey():
    escolhido = fr.pick_allowed(fr.PROTEIN_BOOSTERS, frozenset({"whey"}))
    assert escolhido is not None, "sobrou sem reforço proteico nenhum"
    assert "whey" not in escolhido.query.lower()


@pytest.mark.parametrize("grupo", sorted(TODOS_OS_GRUPOS))
def test_nenhum_grupo_essencial_fica_vazio_com_tudo_marcado(grupo):
    """A regra que protege o produto: restrição TIRA opção, nunca ZERA a vaga.
    Um cardápio sem fonte de proteína não é uma dieta restritiva — é um bug."""
    assert fr.pick_allowed(TODOS_OS_GRUPOS[grupo], frozenset(TUDO)) is not None


def test_normalize_aceita_o_jeito_que_a_pessoa_escreve():
    assert fr.normalize_tokens(["Sem Lactose"]) == [fr.SEM_LACTOSE]
    assert fr.normalize_tokens(["sem whey"]) == ["whey"]
    assert fr.normalize_tokens(["batata-doce"]) == ["batata_doce"]
    # Repetido não duplica; vazio não entra.
    assert fr.normalize_tokens(["vegano", "vegano", "", None]) == [fr.VEGANO]


def test_o_que_o_motor_nao_resolve_e_declarado_e_nao_engolido():
    assert fr.normalize_tokens(["halal"]) == []
    assert fr.unsupported(["halal", "low_carb"]) == ["halal", "low_carb"]
    # "Frutos do mar" o catálogo já atende (não há nenhum) — avisar seria ruído.
    assert fr.unsupported(["sem_frutos_do_mar", "cogumelo"]) == []


def test_perfil_junta_restricoes_e_alimentos_rejeitados():
    class Perfil:
        dietary_restrictions = ["sem_lactose"]
        food_dislikes_list = ["whey", "banana"]

    saida = de.profile_restrictions(Perfil(), extras=["vegano"])
    assert set(saida) == {"sem_lactose", "whey", "banana", "vegano"}


def test_perfil_ausente_nao_quebra():
    assert de.profile_restrictions(None) == []


# --- Como o prato é montado -------------------------------------------------

def _food(nome, macro, grams, slot):
    """Alimento já resolvido, com macros irrelevantes: aqui só interessa PARA
    QUAL refeição ele vai e com quantas gramas."""
    return de._Food(
        food_id=abs(hash(nome)) % 10_000, name=nome, macro=macro,
        kcal100=100.0, p100=10.0, c100=10.0, f100=1.0,
        grams=grams, meals=(), slot=slot,
    )


def _dia_tipico():
    return [
        _food("brócolis", "veg", 150, "main"),
        _food("frango", "protein", 240, "main"),
        _food("arroz", "carb", 330, "main"),
        _food("batata doce", "carb", 380, "main"),
        _food("azeite", "fat", 40, "main"),
        _food("banana", "fruit", 120, "snack"),
        _food("leite", "dairy", 170, "snack"),
        _food("whey", "protein", 60, "snack"),
        _food("aveia", "carb", 140, "snack"),
    ]


def _por_refeicao(meals):
    return {m["category"]: [i["food_name"] for i in m["items"]] for m in meals}


def test_refeicao_principal_nao_passa_de_quatro_itens():
    meals = de._distribute(_dia_tipico(), de._meals_for_count(4))
    por = _por_refeicao(meals)
    assert len(por[fr.ALMOCO]) <= 4, por[fr.ALMOCO]
    assert len(por[fr.JANTAR]) <= 4, por[fr.JANTAR]


def test_cada_refeicao_principal_recebe_um_carboidrato():
    """Menos itens não pode virar jantar sem carboidrato."""
    por = _por_refeicao(de._distribute(_dia_tipico(), de._meals_for_count(4)))
    assert "arroz" in por[fr.ALMOCO] and "batata doce" not in por[fr.ALMOCO]
    assert "batata doce" in por[fr.JANTAR] and "arroz" not in por[fr.JANTAR]


def test_proteina_e_vegetal_seguem_nas_duas_refeicoes():
    por = _por_refeicao(de._distribute(_dia_tipico(), de._meals_for_count(4)))
    for item in ("frango", "brócolis", "azeite"):
        assert item in por[fr.ALMOCO] and item in por[fr.JANTAR]


def test_cafe_e_lanche_deixam_de_ser_identicos():
    por = _por_refeicao(de._distribute(_dia_tipico(), de._meals_for_count(4)))
    assert sorted(por[fr.CAFE]) != sorted(por[fr.LANCHE])


def test_carboidrato_sozinho_volta_a_ser_rateado():
    """Com UM carbo principal, o rodízio deixaria uma das refeições sem ele —
    então ele volta a ser dividido entre as duas."""
    foods = [f for f in _dia_tipico() if f.name != "batata doce"]
    por = _por_refeicao(de._distribute(foods, de._meals_for_count(4)))
    assert "arroz" in por[fr.ALMOCO] and "arroz" in por[fr.JANTAR]


def test_as_gramas_do_dia_nao_mudam_com_o_rodizio():
    """Rodízio é decisão de APRESENTAÇÃO. Se ele mexesse no total, mudaria a
    dieta da pessoa sem ela pedir."""
    foods = _dia_tipico()
    esperado = {f.name: de._round_g(f.grams) for f in foods}
    servido: dict[str, float] = {}
    for meal in de._distribute(foods, de._meals_for_count(4)):
        for item in meal["items"]:
            servido[item["food_name"]] = servido.get(item["food_name"], 0.0) + item["quantity_g"]
    for nome, gramas in esperado.items():
        # tolerância = o arredondamento de 5g por refeição
        assert abs(servido.get(nome, 0.0) - gramas) <= 5, nome


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_nenhuma_combinacao_de_refeicoes_deixa_o_dia_vazio(n):
    meals = de._distribute(_dia_tipico(), de._meals_for_count(n))
    assert meals, f"{n} refeições produziu um dia sem nada"
    assert all(m["items"] for m in meals)


@pytest.mark.parametrize(
    "combo",
    [set(c) for c in itertools.combinations([v for v, _ in RESTRICOES], 2)],
)
def test_duas_restricoes_juntas_nunca_esvaziam_o_catalogo(combo):
    r = frozenset(fr.normalize_tokens(combo))
    for nome, grupo in TODOS_OS_GRUPOS.items():
        assert fr.pick_allowed(grupo, r) is not None, f"{combo} esvaziou {nome}"
