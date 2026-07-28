"""Tempo no fuso do USUÁRIO — a base de "que dia é este registro?".

Por que existe: o app guardava tudo em UTC e fatiava o dia em UTC também
(`logged_at.date()`, `datetime.combine(day, time.min, tzinfo=utc)`). No Brasil
(UTC-3) isso joga tudo o que é registrado depois das 21h para o dia SEGUINTE —
era o bug do "alimento salvo no dia errado" e, por tabela, o que sujava as
médias diárias.

A regra do produto (spec §9.3 e §10.1): **o dia é o dia do calendário da
pessoa**, no fuso dela — não o dia UTC nem a hora do servidor.

O instante continua sendo guardado em UTC no banco (é o certo: um instante é um
instante). O que muda é que a *fatia* de um dia passa por aqui.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Fuso padrão do produto (mercado brasileiro). Só é usado quando o perfil ainda
# não informou o dele — o app manda o fuso do aparelho no login.
DEFAULT_TZ = "America/Sao_Paulo"

_cache: dict[str, ZoneInfo] = {}


def resolve_tz(name: str | None) -> ZoneInfo:
    """Nome IANA -> ZoneInfo, com cache e fallback seguro. Nunca levanta: um
    fuso inválido vindo de um aparelho estranho não pode derrubar a API."""
    key = (name or "").strip() or DEFAULT_TZ
    tz = _cache.get(key)
    if tz is not None:
        return tz
    try:
        tz = ZoneInfo(key)
    except (ZoneInfoNotFoundError, ValueError):
        tz = _cache.get(DEFAULT_TZ) or ZoneInfo(DEFAULT_TZ)
        key = DEFAULT_TZ
    _cache[key] = tz
    return tz


def profile_tz(profile) -> ZoneInfo:
    """Fuso do perfil do usuário (ou o padrão quando ele não tem perfil)."""
    return resolve_tz(getattr(profile, "timezone", None) if profile is not None else None)


def as_utc(dt: datetime) -> datetime:
    """Datetime do banco -> ciente de fuso. SQLite devolve naive mesmo em
    colunas `DateTime(timezone=True)`; nesse caso o valor gravado é UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def local_date(dt: datetime, tz: ZoneInfo) -> date:
    """O DIA DE CALENDÁRIO daquele instante, no fuso da pessoa. É isto que
    substitui os `logged_at.date()` espalhados pelo código."""
    return as_utc(dt).astimezone(tz).date()


def local_now(tz: ZoneInfo) -> datetime:
    return datetime.now(timezone.utc).astimezone(tz)


def today_local(tz: ZoneInfo) -> date:
    """Que dia é hoje PRA PESSOA. Base da regra "o dia de hoje não entra nas
    médias enquanto estiver em andamento" (spec §10.1)."""
    return local_now(tz).date()


def day_bounds_utc(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[início, fim] em UTC do dia de calendário `day` no fuso da pessoa —
    pronto pra entrar num BETWEEN de `logged_at`."""
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=tz).astimezone(timezone.utc)
    return start, end


def window_start_utc(days: int, tz: ZoneInfo) -> datetime:
    """Início (UTC) da janela dos últimos `days` dias de calendário da pessoa,
    incluindo hoje. `days=7` -> meia-noite local de 6 dias atrás."""
    first = today_local(tz) - timedelta(days=max(days, 1) - 1)
    return day_bounds_utc(first, tz)[0]
