"""Corrige exclusão de rotina: workout_sessions.routine_id vira nullable com
ON DELETE SET NULL (era NOT NULL sem regra, então excluir uma rotina já usada
em algum treino quebrava com FOREIGN KEY constraint failed / 500).

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table: necessário no SQLite (não suporta ALTER COLUMN nem
    # adicionar ON DELETE a uma FK existente sem recriar a tabela); no
    # Postgres funciona como um ALTER TABLE normal.
    with op.batch_alter_table("workout_sessions") as batch_op:
        batch_op.alter_column("routine_id", existing_type=sa.Integer(), nullable=True)
        batch_op.drop_constraint("fk_workout_sessions_routine_id_routines", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_workout_sessions_routine_id_routines",
            "routines",
            ["routine_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("workout_sessions") as batch_op:
        batch_op.drop_constraint("fk_workout_sessions_routine_id_routines", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_workout_sessions_routine_id_routines", "routines", ["routine_id"], ["id"]
        )
        batch_op.alter_column("routine_id", existing_type=sa.Integer(), nullable=False)
