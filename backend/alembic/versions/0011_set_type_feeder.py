"""Novo tipo de série "feeder" (preparatória) — badge rápido A/P/F na execução

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE não pode ser revertido nem usado na mesma
    # transação em que foi criado — mas rodar sozinho (sem usar o valor
    # novo depois) funciona normalmente dentro da migração no Postgres.
    op.execute("ALTER TYPE set_type ADD VALUE IF NOT EXISTS 'feeder'")


def downgrade() -> None:
    # Postgres não suporta remover valor de enum — down é no-op (o valor
    # "feeder" fica no tipo, só não é mais usado por código novo).
    pass
