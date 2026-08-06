"""O coach aprendendo com os dados — e, principalmente, sabendo NÃO aprender.

Um motor adaptativo mal contido é pior que um motor fixo: ele erra com números
diferentes toda semana e a pessoa perde a régua. O que este arquivo protege são
as cinco regras do módulo, nesta ordem de importância:

  1. sem evidência suficiente, o parâmetro NÃO age (o coach usa a fórmula);
  2. o observado MISTURA com a fórmula, nunca a substitui;
  3. limites duros — dado estranho não vira prescrição absurda;
  4. passo máximo — o valor não salta de uma leitura pra outra;
  5. todo valor carrega a evidência que o justifica.

A parte de energia é função pura (recebe números já calculados), então roda sem
banco. As que leem histórico são exercitadas no script de integração.
"""

from __future__ import annotations

import pytest

from app.coaching import adaptive as ad

# Uma pessoa com histórico bom: 3 semanas registrando comida, pesagens
# frequentes. Cada teste muda UMA coisa a partir daqui.
BOM = dict(
    kcal_medio=2400.0,
    kcal_confianca="alta",
    dias_comida=21,
    trend_kg_semana=-0.5,
    pontos_peso=12,
    janela_peso_dias=28,
    tdee_formula=2700.0,
)


# --- Regra 1: sem evidência, não age ---------------------------------------

@pytest.mark.parametrize(
    "campo,valor",
    [
        ("kcal_medio", None),
        ("trend_kg_semana", None),
        ("dias_comida", ad.MIN_DIAS_COMIDA - 1),
        ("pontos_peso", ad.MIN_PONTOS_PESO - 1),
        ("janela_peso_dias", ad.MIN_JANELA_PESO_DIAS - 1),
        ("kcal_confianca", "insuficiente"),
    ],
)
def test_sem_evidencia_o_coach_usa_a_formula(campo, valor):
    a = ad.energia_observada(**{**BOM, campo: valor})
    assert not a.usar
    assert a.aplicar(2700.0) == 2700.0
    assert a.evidencia, "recusar sem explicar é pior do que recusar"


def test_o_dia_zero_nao_inventa_nada():
    a = ad.energia_observada(
        kcal_medio=None, kcal_confianca="insuficiente", dias_comida=0,
        trend_kg_semana=None, pontos_peso=0, janela_peso_dias=0, tdee_formula=2700.0,
    )
    assert a.confianca == ad.NENHUMA
    assert a.aplicar(2700.0) == 2700.0


# --- A conta em si ----------------------------------------------------------

def test_quem_perde_peso_comendo_pouco_gasta_mais_do_que_a_formula_diz():
    """Come 2.400 e perde 0,5 kg/semana => gasta ~2.950. A balança é o juiz."""
    a = ad.energia_observada(**BOM)
    assert a.usar
    esperado = 2400 + 0.5 * ad.KCAL_POR_KG / 7
    assert a.valor == pytest.approx(esperado, abs=1)
    assert a.valor > BOM["tdee_formula"]


def test_quem_mantem_o_peso_gasta_o_que_come():
    a = ad.energia_observada(**{**BOM, "trend_kg_semana": 0.0, "tdee_formula": 2400.0})
    assert a.valor == pytest.approx(2400.0, abs=1)


def test_quem_ganha_peso_gasta_menos_do_que_come():
    a = ad.energia_observada(**{**BOM, "kcal_medio": 3000.0, "trend_kg_semana": 0.3,
                                "tdee_formula": 2800.0})
    assert a.valor < 3000.0


# --- Regra 2: mistura, não substitui ---------------------------------------

def test_o_observado_nunca_substitui_a_formula_por_inteiro():
    a = ad.energia_observada(**BOM)
    usado = a.aplicar(BOM["tdee_formula"])
    menor, maior = sorted([BOM["tdee_formula"], a.valor])
    assert menor < usado < maior, "o valor usado tem que ficar ENTRE fórmula e observado"


def test_mais_evidencia_puxa_mais_para_o_observado():
    poucos = ad.energia_observada(**{**BOM, "dias_comida": 10, "pontos_peso": 4})
    muitos = ad.energia_observada(**BOM)
    assert muitos.peso > poucos.peso
    f = BOM["tdee_formula"]
    assert abs(muitos.aplicar(f) - f) > abs(poucos.aplicar(f) - f)


def test_a_confianca_e_a_do_elo_mais_fraco():
    """Peso perfeito não compensa comida mal registrada."""
    a = ad.energia_observada(**{**BOM, "dias_comida": 10})
    assert a.confianca == ad.BAIXA


# --- Regra 3: limites duros -------------------------------------------------

def test_registro_furado_nao_vira_prescricao_absurda():
    """Quem registra 900 kcal/dia e não perde peso 'gasta' 900 pela conta crua.
    O limite segura isso — é sub-registro, não metabolismo."""
    a = ad.energia_observada(**{**BOM, "kcal_medio": 900.0, "trend_kg_semana": 0.0})
    assert a.valor >= BOM["tdee_formula"] * ad.TDEE_MIN_FATOR - 1
    assert "limitei" in a.evidencia


def test_o_teto_tambem_segura():
    a = ad.energia_observada(**{**BOM, "kcal_medio": 6000.0, "trend_kg_semana": -1.0})
    assert a.valor <= BOM["tdee_formula"] * ad.TDEE_MAX_FATOR + 1


@pytest.mark.parametrize("kcal", [500, 1200, 2000, 3500, 6000])
@pytest.mark.parametrize("trend", [-1.5, -0.5, 0.0, 0.4, 1.2])
def test_nenhuma_combinacao_sai_da_faixa_segura(kcal, trend):
    a = ad.energia_observada(**{**BOM, "kcal_medio": float(kcal), "trend_kg_semana": trend})
    f = BOM["tdee_formula"]
    assert f * ad.TDEE_MIN_FATOR - 1 <= a.valor <= f * ad.TDEE_MAX_FATOR + 1
    # E o valor USADO também, que é o que vira meta.
    assert f * ad.TDEE_MIN_FATOR - 1 <= a.aplicar(f) <= f * ad.TDEE_MAX_FATOR + 1


# --- Regra 4: passo máximo --------------------------------------------------

def test_o_valor_nao_salta_de_uma_leitura_para_a_outra():
    """Coach que muda tudo toda semana não é adaptativo, é instável."""
    a = ad.energia_observada(**{**BOM, "tdee_anterior": 2500.0})
    assert a.valor <= 2500.0 * (1 + ad.TDEE_PASSO) + 0.01


def test_sem_valor_anterior_o_primeiro_calculo_e_aceito():
    a = ad.energia_observada(**{**BOM, "tdee_anterior": None})
    assert a.valor == pytest.approx(2400 + 0.5 * ad.KCAL_POR_KG / 7, abs=1)


def test_leituras_repetidas_convergem_em_vez_de_oscilar():
    """Aplicando o passo máximo repetidamente, o valor caminha PARA o observado
    e para lá — não fica indo e voltando."""
    anterior = 2400.0
    for _ in range(30):
        a = ad.energia_observada(**{**BOM, "tdee_anterior": anterior})
        novo = a.valor
        assert novo >= anterior - 0.01, "andou pra trás: está oscilando"
        if abs(novo - anterior) < 0.5:
            break
        anterior = novo
    alvo = min(2400 + 0.5 * ad.KCAL_POR_KG / 7, BOM["tdee_formula"] * ad.TDEE_MAX_FATOR)
    assert anterior == pytest.approx(alvo, abs=5)


# --- Regra 5: evidência -----------------------------------------------------

def test_todo_valor_usado_sabe_se_explicar():
    """A evidência precisa citar os números de onde o valor saiu.

    Os trechos cobrados são em LINGUAGEM DE GENTE ("kcal por dia", vírgula
    decimal), não na notação técnica de antes ("kcal/dia", "0.50 kg/semana"): o
    texto foi reescrito de propósito pra tela e o teste tinha ficado preso à
    forma antiga. O que o teste protege é que os números apareçam — não a
    pontuação com que eles são escritos."""
    a = ad.energia_observada(**BOM)
    assert a.usar
    for pedaco in ("2400", "kcal por dia", "0,50 kg por semana"):
        assert pedaco in a.evidencia, a.evidencia


def test_o_dicionario_tem_o_que_a_tela_precisa():
    d = ad.energia_observada(**BOM).to_dict()
    assert set(d) == {"chave", "valor", "confianca", "evidencia", "n"}


# --- Contrato do Aprendido --------------------------------------------------

def test_peso_zero_quando_nao_ha_confianca():
    a = ad.Aprendido("x", 999.0, ad.NENHUMA, "", 0)
    assert a.peso == 0.0 and a.aplicar(10.0) == 10.0


@pytest.mark.parametrize("conf", [ad.BAIXA, ad.MEDIA, ad.ALTA])
def test_o_observado_nunca_pesa_100_por_cento(conf):
    assert 0 < ad.PESO_POR_CONFIANCA[conf] < 1.0


def test_mais_confianca_pesa_mais():
    p = ad.PESO_POR_CONFIANCA
    assert p[ad.NENHUMA] < p[ad.BAIXA] < p[ad.MEDIA] < p[ad.ALTA]


# --- Faixas dos outros parâmetros ------------------------------------------

def test_tolerancia_a_volume_e_um_ajuste_fino_e_nao_uma_reescrita():
    """±25% no máximo: o aprendizado afina a prescrição, não reescreve os
    landmarks MEV/MRV, que são fisiologia e não preferência."""
    assert 0.7 <= ad.TOLERANCIA_MIN < 1.0 < ad.TOLERANCIA_MAX <= 1.3


def test_o_passo_de_carga_aprendido_fica_em_faixa_de_academia():
    assert ad.PASSO_MIN_KG >= 1.0
    assert ad.PASSO_MAX_KG <= 25.0


def test_o_ritmo_por_serie_fica_em_faixa_humana():
    assert ad.SEG_POR_SERIE_MIN >= 45
    assert ad.SEG_POR_SERIE_MAX <= 600


def test_modelo_vazio_nao_fala_no_prompt():
    """Sem nada aprendido, o coach não gasta contexto dizendo que não sabe."""
    nada = ad.Aprendido("x", 0.0, ad.NENHUMA, "", 0)
    m = ad.ModeloAprendido(energia=nada, tolerancia_volume=nada, ritmo_sessao=nada)
    assert m.prompt_lines() == []
    assert m.to_dict()["aprendidos"] == []


def test_modelo_com_aprendizado_entra_no_prompt_com_a_evidencia():
    a = ad.energia_observada(**BOM)
    nada = ad.Aprendido("x", 0.0, ad.NENHUMA, "", 0)
    m = ad.ModeloAprendido(energia=a, tolerancia_volume=nada, ritmo_sessao=nada)
    linhas = "\n".join(m.prompt_lines())
    assert a.evidencia in linhas
    assert m.to_dict()["aprendidos"] == ["energia"]
