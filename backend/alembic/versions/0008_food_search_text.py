"""Busca de alimentos sem acento: coluna normalizada foods.search_text

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-08

"""
import unicodedata
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize(*parts: str | None) -> str:
    raw = " ".join(p for p in parts if p)
    nfkd = unicodedata.normalize("NFKD", raw)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(ascii_only.lower().split())


def upgrade() -> None:
    op.add_column(
        "foods",
        sa.Column("search_text", sa.String(length=400), nullable=False, server_default=""),
    )
    op.create_index("ix_foods_search_text", "foods", ["search_text"])

    # Backfill dos alimentos já existentes (a normalização precisa de Python;
    # não dá pra fazer só em SQL sem a extensão unaccent).
    bind = op.get_bind()
    foods = bind.execute(sa.text("SELECT id, name, brand FROM foods")).fetchall()
    for fid, name, brand in foods:
        bind.execute(
            sa.text("UPDATE foods SET search_text = :st WHERE id = :id"),
            {"st": _normalize(name, brand), "id": fid},
        )


def downgrade() -> None:
    op.drop_index("ix_foods_search_text", table_name="foods")
    op.drop_column("foods", "search_text")
