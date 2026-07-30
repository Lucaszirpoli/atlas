"""A limpeza dos alimentos, e a regra que impede a base de sujar de novo.

O relato que originou isto: pesquisar "cuscuz" trazia vários resultados sem
marca, com calorias de 112 a 354, e nada no nome dizendo qual era cru e qual era
cozido. A causa era `search_brands_live` GRAVAR todo resultado do Open Food
Facts como alimento permanente, inclusive os que vêm sem marca preenchida.

Os testes cobrem as duas metades: a regra de classificação (o que é duplicata,
o que é alimento diferente) e a extração da marca de dentro do nome.
"""

from __future__ import annotations

from app.scripts import dedup_foods as dd
from app.services.open_food_facts import _marca_no_nome


# --- Marca escondida no nome ----------------------------------------------
def test_extrai_marca_do_nome():
    assert _marca_no_nome("Cuzcuz - Gostozin", None) == ("Cuzcuz", "Gostozin")
    assert _marca_no_nome("Creme de ricota light ervas finas - Godam", None) == (
        "Creme de ricota light ervas finas",
        "Godam",
    )


def test_nao_confunde_qualificador_com_marca():
    """"Arroz - integral" não tem marca "integral" — isso é o tipo do arroz."""
    for nome in ("Arroz - integral", "Leite - desnatado", "Biscoito - sem glúten",
                 "Peito de frango - cru", "Requeijão - light"):
        _, marca = _marca_no_nome(nome, None)
        assert marca is None, f"{nome} não deveria virar marca"


def test_marca_existente_nunca_e_sobrescrita():
    assert _marca_no_nome("Cuzcuz - Gostozin", "Nestlé") == ("Cuzcuz - Gostozin", "Nestlé")


def test_nome_sem_separador_fica_intacto():
    assert _marca_no_nome("Bolo de rolo", None) == ("Bolo de rolo", None)
    assert _marca_no_nome("Espaguete com ovos (cru)", None) == ("Espaguete com ovos (cru)", None)


def test_cauda_longa_nao_e_marca():
    """4 palavras é o limite: mais que isso é frase, não marca."""
    _, marca = _marca_no_nome("Bolo - feito com farinha de trigo integral especial", None)
    assert marca is None


# --- O que é a MESMA comida ------------------------------------------------
def test_sal_nao_muda_a_comida():
    """Só o sal separando os dois nomes: é a mesma comida (o caso do cuscuz)."""
    assert dd._base("Cuscuz de milho cozido") == dd._base("Cuscuz de milho cozido com sal")
    assert dd._base("Amendoim torrado") == dd._base("Amendoim torrado salgado")
    assert dd._base("Castanha de caju torrada") == dd._base("Castanha-de-caju torrada salgada")


def test_preparo_muda_a_comida():
    """Cru e cozido NÃO são a mesma comida — arroz cru tem quase 3x as calorias."""
    assert dd._base("Arroz branco cru") != dd._base("Arroz branco cozido")
    assert dd._distintivos("Arroz branco cru") != dd._distintivos("Arroz branco cozido")


def test_pele_e_casca_contam_como_distintivo():
    """"com pele" e "sem pele" mudam as calorias de verdade (frango: 260 x 233)."""
    assert dd._distintivos("Frango sobrecoxa com pele assada") != dd._distintivos(
        "Frango sobrecoxa sem pele assada"
    )


def test_base_nua_agrupa_as_variantes_de_preparo():
    """A chave que revela AMBIGUIDADE: as três sobrecoxas caem no mesmo grupo, e
    aí dá pra ver que a que não diz nada sobre a pele é a ambígua."""
    nomes = [
        "Frango sobrecoxa assada",
        "Frango sobrecoxa com pele assada",
        "Frango sobrecoxa sem pele assada",
    ]
    assert len({dd._base_nua(n) for n in nomes}) == 1


def test_base_nua_nao_confunde_alimentos_diferentes():
    assert dd._base_nua("Pão de queijo") != dd._base_nua("Pão de batata")
    assert dd._base_nua("Frango sobrecoxa assada") != dd._base_nua("Frango peito assado")


# --- Quem ganha o empate ---------------------------------------------------
def test_taco_ganha_do_open_food_facts():
    """Tabela oficial brasileira na frente de rótulo digitado por voluntário."""
    from app.models.food import FoodSource

    class F:
        def __init__(self, source, name, id):
            self.source, self.name, self.id = source, name, id

    taco = F(FoodSource.TACO, "Pão integral", 11)
    off = F(FoodSource.OPEN_FOOD_FACTS, "Pão integral", 1038)
    assert dd._qualidade(taco) < dd._qualidade(off)


def test_nome_mais_curto_ganha_dentro_da_mesma_fonte():
    from app.models.food import FoodSource

    class F:
        def __init__(self, source, name, id):
            self.source, self.name, self.id = source, name, id

    curto = F(FoodSource.TACO, "Amendoim torrado", 152)
    longo = F(FoodSource.TACO, "Amendoim torrado salgado", 808)
    assert dd._qualidade(curto) < dd._qualidade(longo)


# --- Normalização ---------------------------------------------------------
def test_norm_ignora_acento_e_pontuacao():
    assert dd._norm("Pão integral") == dd._norm("Pao integral")
    assert dd._norm("Castanha-de-caju") == dd._norm("Castanha de caju")
