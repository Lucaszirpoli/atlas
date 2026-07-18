from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def handle_is_available(db: Session, handle: str, exclude_user_id: int | None = None) -> bool:
    stmt = select(User.id).where(User.handle == handle)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return db.execute(stmt).first() is None


def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_by_handle(db: Session, handle: str) -> User | None:
    return db.execute(select(User).where(User.handle == handle)).scalar_one_or_none()


def get_by_email_or_handle(db: Session, identifier: str) -> User | None:
    """A tela de login pede "e-mail ou usuário". @handle nunca tem "@" no
    meio (regex de cadastro é `[a-z0-9_]{3,30}`), então usar "@" pra decidir
    o caminho é seguro e evita duas queries pra quem digitou e-mail."""
    identifier = identifier.strip()
    if "@" in identifier:
        return get_by_email(db, identifier.lower())
    return get_by_handle(db, identifier.lower())
