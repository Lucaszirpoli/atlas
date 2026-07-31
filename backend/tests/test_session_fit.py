"""O TEMPO POR SESSÃO como restrição de verdade.

Antes, "Tempo por sessão" mandava só no número de EXERCÍCIOS (5/6/8) e não
encostava no número de séries: quem escolhia Curto e quem escolhia Longo pedia a
mesma quantidade de séries por músculo, e o Curto só espremia o mesmo volume em
menos exercícios. É a receita do treino apertado com músculo ficando sem vaga.

Aqui o tempo escolhido é cobrado nas três coisas que ele deveria mandar:
a MARGEM de volume, o AVISO de cobertura, e a escolha de TÉCNICA.
"""

from __future__ import annotations

import pytest

from app.coaching import session_fit, training_brain, volume_landmarks
from app.models.exercise import MuscleGroup as M

TEMPOS = ("curto", "medio", "longo")


# --- A margem cresce com o tempo -------------------------------------------
@pytest.mark.parametrize("musculo", (M.CHEST, M.BACK, M.QUADS))
def test_margem_de_volume_cresce_com_o_tempo_de_sessao(musculo):
    """Curto trabalha no piso da faixa, Longo na parte alta. É a tradução direta
    de "sua margem aumenta conforme o tempo de treino"."""
    alvos = [
        volume_landmarks.weekly_target_sets(
            musculo, "intermediario", 0, session_length=t
        )
        for t in TEMPOS
    ]
    assert alvos[0] < alvos[1] < alvos[2], dict(zip(TEMPOS, alvos))
    assert alvos[0] == volume_landmarks.BASE_MIN, "Curto deveria partir do piso da faixa"


@pytest.mark.parametrize("tempo", TEMPOS)
def test_ponto_fraco_nao_encolhe_com_o_relogio(tempo):
    """A exceção deliberada: prioridade mantém a faixa alta em QUALQUER tempo.

    Num treino curto o que se espreme é o que não é prioridade. Espremer os dois
    lados igualmente devolveria o problema original — marcar um ponto fraco e não
    ver diferença — só que por outro caminho.
    """
    alvo = volume_landmarks.weekly_target_sets(
        M.BICEPS, "intermediario", 0, priority="alta", session_length=tempo
    )
    base = volume_landmarks.weekly_target_sets(
        M.BICEPS, "intermediario", 0, priority="normal", session_length=tempo
    )
    assert alvo >= volume_landmarks.WEAK_MIN
    assert alvo > base, f"em {tempo} o ponto fraco não ficou acima da faixa-base"


def test_curto_pede_menos_trabalho_que_longo_no_total():
    """A soma da semana, não um músculo isolado — é o que a pessoa sente."""
    musculos = [M.CHEST, M.BACK, M.SHOULDERS, M.QUADS, M.HAMSTRINGS, M.GLUTES]
    totais = {
        t: sum(volume_landmarks.weekly_plan(musculos, "intermediario", 0, session_length=t).values())
        for t in TEMPOS
    }
    assert totais["curto"] < totais["medio"] < totais["longo"], totais


# --- O aviso de cobertura --------------------------------------------------
def test_combinacao_folgada_nao_avisa_nada():
    """Aviso que aparece sempre vira ruído que ninguém lê."""
    assert session_fit.aviso(5, "longo") is None
    assert session_fit.aviso(6, "longo") is None


def test_combinacao_apertada_avisa_e_recomenda():
    """3 dias × 5 exercícios são 15 vagas pra 10 grupos: não cabe. A pessoa pode
    escolher assim mesmo — mas precisa saber antes, não depois de seis semanas."""
    texto = session_fit.aviso(3, "curto")
    assert texto is not None
    assert "Panturrilha" in texto
    assert "Longo" in texto, "o aviso tem que recomendar um tempo que resolva"


def test_aviso_nao_cobra_musculo_que_o_coach_vai_cobrir():
    """Ponto fraco tem exercício garantido em qualquer configuração
    (test_ponto_fraco_sempre_tem_exercicio_dedicado). Avisar sobre ele seria
    mentira."""
    sem_prioridade = session_fit.aviso(3, "curto")
    com_prioridade = session_fit.aviso(3, "curto", weak_points=["calves"])
    assert "Panturrilha" in (sem_prioridade or "")
    assert "Panturrilha" not in (com_prioridade or "")


def test_recomendacao_e_o_menor_tempo_que_resolve():
    """Recomendar Longo quando Médio já cobria empurraria a pessoa pra um treino
    mais comprido do que ela precisa."""
    assert session_fit.tempo_recomendado(5) == "medio"
    # 2 dias não fecha em tempo nenhum — e aí a recomendação é honesta sobre isso.
    assert session_fit.tempo_recomendado(2) is None
    assert "não cabe tudo em nenhum tempo" in (session_fit.aviso(2, "longo") or "")


# --- Técnica em sessão curta -----------------------------------------------
@pytest.mark.parametrize("periodo", ("acumulacao", "intensificacao"))
@pytest.mark.parametrize("composto", (True, False))
@pytest.mark.parametrize("ponto_fraco", (True, False))
def test_tecnica_de_sessao_curta_nunca_estica_o_treino(periodo, composto, ponto_fraco):
    """A regra que o usuário formulou: numa sessão curta, tudo tem que empurrar
    pro treino ser mais rápido.

    Uma técnica que vale 2 séries substitui 2 séries retas; a pergunta é se ela
    leva menos tempo que elas. O teste cobra a INVARIANTE em vez de fixar qual
    técnica — assim, mexer numa estrutura (já aconteceu: muscle round foi a 6
    blocos) quebra o teste em vez de silenciosamente esticar o treino de quem
    pediu o mais curto.
    """
    chave, _, _ = training_brain.suggest_technique(
        composto, periodo, session_length="curto", is_weak_point=ponto_fraco
    )
    poupado = training_brain.technique_time_saved_s(chave)
    assert poupado is not None and poupado > 0, (
        f"em sessão curta o coach escolheu {chave}, que custa "
        f"{-(poupado or 0)}s a mais que as séries retas equivalentes"
    )
