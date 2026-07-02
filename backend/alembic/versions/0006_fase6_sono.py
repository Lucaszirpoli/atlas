"""Fase 6: sono

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    wake_feeling = sa.Enum("DESCANSADO", "CANSADO", "MUITO_CANSADO", name="wake_feeling")

    op.create_table(
        "sleep_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sleep_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wake_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quality", sa.Integer(), nullable=False),
        sa.Column("wake_feeling", wake_feeling, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sleep_logs_user_sleep_at", "sleep_logs", ["user_id", "sleep_at"])


def downgrade() -> None:
    op.drop_table("sleep_logs")
    sa.Enum(name="wake_feeling").drop(op.get_bind(), checkfirst=True)
