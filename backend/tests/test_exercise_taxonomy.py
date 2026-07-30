"""A taxonomia tem que casar EXATAMENTE com a biblioteca curada.

Se um exercício entra no seed e ninguém o classifica, ele cai no fallback tier
B e nunca vira primeira escolha — o treino piora em silêncio. Se um exercício
sai do seed e a taxonomia continua com ele, a tabela mente. Estes testes são o
que impede as duas coisas.
"""

from __future__ import annotations

from app.ai import exercise_taxonomy as tax
from app.models.exercise import MuscleGroup
from app.scripts.seed_exercises_curated import EXERCISES


SEED_NAMES = {nome for nome, *_ in EXERCISES}


def test_todo_exercicio_curado_tem_taxonomia():
    faltando = sorted(n for n in SEED_NAMES if n not in tax.TAXONOMY)
    assert not faltando, f"exercícios sem tier/padrão/região: {faltando}"


def test_taxonomia_nao_tem_exercicio_fantasma():
    sobrando = sorted(n for n in tax.TAXONOMY if n not in SEED_NAMES)
    assert not sobrando, f"classificados mas fora da biblioteca: {sobrando}"


def test_padrao_bate_com_musculo_primario():
    """Um padrão de perna não pode estar num exercício de peito e vice-versa —
    pega erro de digitação na tabela, que é o risco real de uma lista de 119."""
    P, M = tax.Pattern, MuscleGroup
    permitido = {
        M.CHEST: {P.PUSH_H, P.ISO},
        M.BACK: {P.PULL_H, P.PULL_V, P.ISO},
        M.SHOULDERS: {P.PUSH_V, P.ISO},
        M.BICEPS: {P.ISO},
        M.TRICEPS: {P.ISO, P.PUSH_H, P.PUSH_V},
        M.QUADS: {P.KNEE, P.ISO, P.ADDUCTION},
        M.HAMSTRINGS: {P.HIP, P.KNEE_FLEX},
        M.GLUTES: {P.HIP, P.ISO, P.ABDUCTION},
        M.CALVES: {P.CALF},
        M.ABS: {P.CORE},
    }
    erros = []
    for nome, primario, *_ in EXERCISES:
        t = tax.TAXONOMY.get(nome)
        if t is None:
            continue
        ok = permitido.get(primario)
        if ok is not None and t.pattern not in ok:
            erros.append(f"{nome}: {t.pattern.value} não cabe em {primario.value}")
    assert not erros, erros


def test_cada_musculo_tem_pelo_menos_um_tier_s():
    """Se um músculo não tem nenhuma primeira escolha, o motor é obrigado a
    descer de tier logo na vaga principal — sinal de tabela incompleta."""
    from collections import defaultdict

    por_musculo = defaultdict(list)
    for nome, primario, *_ in EXERCISES:
        t = tax.TAXONOMY.get(nome)
        if t is not None:
            por_musculo[primario].append(t.tier)
    sem_s = sorted(m.value for m, tiers in por_musculo.items() if tax.Tier.S not in tiers)
    assert not sem_s, f"músculos sem nenhum exercício tier S: {sem_s}"


def test_regioes_exigidas_sao_alcancaveis():
    """Toda região que o validador global vai COBRAR precisa existir em algum
    exercício da biblioteca — senão o treino é reprovado por algo impossível."""
    existentes = {t.region for t in tax.TAXONOMY.values()}
    impossiveis = [
        f"{m.value}:{r}"
        for m, regioes in tax.REQUIRED_REGIONS.items()
        for r in regioes
        if r not in existentes
    ]
    assert not impossiveis, f"regiões exigidas sem exercício na base: {impossiveis}"


def test_fallback_nunca_levanta():
    t = tax.taxon_for("Exercício inventado pelo usuário", MuscleGroup.CHEST, True)
    assert t.tier is tax.Tier.B and t.is_compound
    t2 = tax.taxon_for("Outro sem grupo", None, False)
    assert t2.tier is tax.Tier.B


def test_lookup_ignora_acento_e_caixa():
    assert tax.taxon_for("HACK SQUAT").tier is tax.Tier.S
    assert tax.taxon_for("elevacao pelvica na maquina").tier is tax.Tier.S


def test_ordem_das_classes():
    """Composto antes de isolador antes de músculo menor — a espinha do
    Princípio 3. Se isso inverter, a sessão inteira sai errada."""
    assert tax.TAXONOMY["Hack squat"].order_class == tax.ORDER_COMPOUND
    assert tax.TAXONOMY["Cadeira extensora"].order_class == tax.ORDER_ISOLATION
    assert tax.TAXONOMY["Mesa flexora"].order_class == tax.ORDER_ISOLATION
    assert tax.TAXONOMY["Panturrilha em pé"].order_class == tax.ORDER_MINOR
    assert tax.TAXONOMY["Cadeira abdutora"].order_class == tax.ORDER_MINOR
    assert tax.TAXONOMY["Abdominal na polia"].order_class == tax.ORDER_MINOR


def test_pulldown_bracos_estendidos_e_isolado():
    """Regressão: o classificador por palavra-chave marcava este exercício como
    COMPOSTO (por causa do "pulldown"), e ele podia ocupar a vaga de composto de
    costas no lugar de uma remada ou puxada. É extensão de ombro, articulação
    única. Mesmo caso dos dois pullovers."""
    for nome in ("Pulldown com braços estendidos", "Pullover na máquina", "Pullover na polia"):
        assert not tax.TAXONOMY[nome].is_compound, nome


def test_redundancia_do_exemplo_da_spec():
    """O exemplo literal da regra mestra: os 3 supinos retos têm a MESMA função
    (redundante) e o trio inclinado/chest press/peck deck tem 3 funções."""
    redundantes = {
        tax.TAXONOMY["Supino reto com barra"].function_key,
        tax.TAXONOMY["Supino reto no Smith"].function_key,
        tax.TAXONOMY["Chest press"].function_key,
    }
    assert len(redundantes) == 1

    complementares = {
        tax.TAXONOMY["Supino inclinado no Smith"].function_key,
        tax.TAXONOMY["Chest press"].function_key,
        tax.TAXONOMY["Peck deck"].function_key,
    }
    assert len(complementares) == 3
