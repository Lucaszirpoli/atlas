from collections.abc import Generator
from datetime import timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.dialects.sqlite import DATETIME as SQLiteDATETIME
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

# SQLite (usado só em dev local, sem servidor Postgres) precisa de dois ajustes:
# check_same_thread=False para o pool do FastAPI, e o PRAGMA foreign_keys=ON
# para que os ondelete CASCADE/SET NULL dos modelos realmente funcionem.
_is_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    class _SQLiteAwareDateTime(TypeDecorator):
        """SQLite não guarda fuso: uma coluna `DateTime(timezone=True)` volta
        NAIVE (sem tzinfo), mesmo tendo sido gravada em UTC. Sem isto, o
        Pydantic serializa o valor sem `Z`/offset e o app lê como HORÁRIO
        LOCAL em vez de UTC — um registro de sono às 21h15 de ontem (UTC)
        aparece como 21h15 de HOJE (local), virando o dia errado perto da
        meia-noite. Postgres (produção) não tem essa lacuna; este shim só
        entra em dev (`_is_sqlite`). Troca só o `process_result_value`
        (leitura) — grava normalmente, então nenhum model precisa mudar.

        `impl` é o `DATETIME` do PRÓPRIO dialeto sqlite (não o genérico
        `sqlalchemy.types.DateTime`) — é ele quem sabe converter a string
        ISO que o sqlite3 devolve num `datetime` Python; sem isso o
        `process_result_value` abaixo recebia a string crua, não um
        datetime, e quebrava em qualquer leitura."""

        impl = SQLiteDATETIME
        cache_ok = True

        def process_result_value(self, value, dialect):
            if value is not None and value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value

    engine.dialect.colspecs = {**engine.dialect.colspecs, DateTime: _SQLiteAwareDateTime}


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
