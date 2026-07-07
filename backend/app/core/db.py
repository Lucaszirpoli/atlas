from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

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


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
