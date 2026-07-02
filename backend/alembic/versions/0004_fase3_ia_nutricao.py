"""Fase 3: IA de nutricao - chat_messages, weight_logs ja existia (Fase 0)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    chat_role = sa.Enum("USER", "ASSISTANT", name="chat_role")

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", chat_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("proposed_action", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_messages_user_created", "chat_messages", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    sa.Enum(name="chat_role").drop(op.get_bind(), checkfirst=True)
