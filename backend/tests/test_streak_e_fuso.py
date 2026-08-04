"""Sequência ("recorde") e a fatia do dia no fuso da pessoa.

Dois defeitos que o usuário viu no celular e que têm a mesma raiz — o servidor
raciocinando em UTC enquanto o celular vive em America/Sao_Paulo:

  1. o app "achava que hoje é segunda" quando já era terça;
  2. o recorde ficava parado, porque a sequência só contava um dia em que a
     pessoa fechasse METADE dos quatro hábitos.

Aqui não sobe banco: a sequência virou função pura (`compute_streaks`) e a
conversão de dia é `app.core.usertime`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.usertime import day_bounds_utc, local_date, today_local, window_start_utc
from app.routers.coaching import _semana_atual_inicio
from app.routers.evolution import compute_streaks

SP = ZoneInfo("America/Sao_Paulo")


def dias(*ativos, inicio="2026-08-01"):
    """['2026-08-01', ...] com o flag `active` de cada dia."""
    d0 = datetime.fromisoformat(inicio).date()
    return [
        {"date": (d0 + timedelta(days=i)).isoformat(), "active": bool(a)}
        for i, a in enumerate(ativos)
    ]


# --- Sequência --------------------------------------------------------------

def test_qualquer_registro_no_dia_mantem_a_sequencia():
    d = dias(1, 1, 1)
    assert compute_streaks(d, hoje="2026-08-03") == (3, 3)


def test_hoje_ainda_vazio_nao_quebra_a_sequencia():
    """A pessoa abre o app de manhã: ela ainda não registrou nada HOJE, e isso
    não pode zerar 5 dias de constância."""
    d = dias(1, 1, 1, 1, 1, 0)
    assert compute_streaks(d, hoje="2026-08-06") == (5, 5)


def test_um_dia_perdido_no_meio_quebra():
    d = dias(1, 1, 0, 1, 1)
    atual, recorde = compute_streaks(d, hoje="2026-08-05")
    assert atual == 2
    assert recorde == 2


def test_recorde_guarda_a_melhor_sequencia_passada():
    d = dias(1, 1, 1, 1, 0, 1)
    atual, recorde = compute_streaks(d, hoje="2026-08-06")
    assert atual == 1
    assert recorde == 4


def test_recorde_nunca_fica_abaixo_da_sequencia_atual():
    """Janela cortada: todos os dias visíveis são ativos, e a sequência real
    começou antes da janela. O recorde não pode mostrar menos que o atual."""
    d = dias(*([1] * 30))
    atual, recorde = compute_streaks(d, hoje=d[-1]["date"])
    assert atual == 30 and recorde == 30


def test_sem_nenhum_registro_e_zero_e_nao_explode():
    assert compute_streaks(dias(0, 0, 0), hoje="2026-08-03") == (0, 0)
    assert compute_streaks([], hoje="2026-08-03") == (0, 0)


# --- Que dia é hoje ---------------------------------------------------------

def test_registro_da_noite_pertence_ao_dia_de_ontem_e_nao_ao_de_amanha():
    """22h de terça em São Paulo = 01h de quarta em UTC. Fatiar em UTC jogava
    esse jantar pra quarta — e era o que fazia o app discordar do calendário
    do celular."""
    instante = datetime(2026, 8, 4, 22, 30, tzinfo=SP).astimezone(timezone.utc)
    assert instante.date().isoformat() == "2026-08-05"      # o que o UTC dizia
    assert local_date(instante, SP).isoformat() == "2026-08-04"  # o que vale


def test_janela_comeca_na_meia_noite_local_e_nao_na_de_greenwich():
    inicio = window_start_utc(7, SP)
    assert inicio.astimezone(SP).hour == 0
    assert local_date(inicio, SP) == today_local(SP) - timedelta(days=6)


def test_limites_do_dia_cobrem_o_dia_inteiro_da_pessoa():
    dia = today_local(SP)
    ini, fim = day_bounds_utc(dia, SP)
    assert local_date(ini, SP) == dia and local_date(fim, SP) == dia
    assert (fim - ini) < timedelta(days=1)


def test_semana_comeca_no_domingo_da_pessoa_nao_no_do_servidor():
    """Domingo 21h em SP já é segunda em UTC. Sem fuso, o check-in começava a
    contar uma semana que pra ela ainda nem tinha virado."""
    domingo_a_noite = datetime(2026, 8, 2, 21, 30, tzinfo=SP).astimezone(timezone.utc)
    inicio = _semana_atual_inicio(domingo_a_noite, SP)
    local = inicio.astimezone(SP)
    assert local.date().isoformat() == "2026-08-02"  # o próprio domingo
    assert (local.hour, local.minute) == (0, 0)


def test_semana_no_meio_da_semana_volta_ao_domingo_anterior():
    terca = datetime(2026, 8, 4, 10, 0, tzinfo=SP).astimezone(timezone.utc)
    local = _semana_atual_inicio(terca, SP).astimezone(SP)
    assert local.date().isoformat() == "2026-08-02"
