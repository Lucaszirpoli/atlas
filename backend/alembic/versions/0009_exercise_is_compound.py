"""Classificação composto/isolado: coluna exercises.is_compound

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exercises",
        sa.Column("is_compound", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    # Backfill: reaproveita o classificador da aplicação (nome PT + secundários).
    from app.services.exercise_classify import classify_is_compound

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, name, secondary_muscle_groups FROM exercises")
    ).fetchall()
    for rid, name, secondary in rows:
        # secondary pode vir como lista (ARRAY pg) ou string JSON (sqlite) —
        # o classificador só precisa saber se está vazio, então tratamos ambos.
        groups = secondary if isinstance(secondary, (list, tuple)) else (secondary or [])
        is_comp = classify_is_compound(name, groups, None)
        bind.execute(
            sa.text("UPDATE exercises SET is_compound = :v WHERE id = :id"),
            {"v": is_comp, "id": rid},
        )


def downgrade() -> None:
    op.drop_column("exercises", "is_compound")
