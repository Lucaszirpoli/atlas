"""Fase 0: fundacao - users, user_profiles, weight_logs, consent_records

Revision ID: 0001
Revises:
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    auth_provider = sa.Enum("EMAIL", "GOOGLE", "APPLE", name="auth_provider")
    plan = sa.Enum("FREE", "PRO", name="plan")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("auth_provider", auth_provider, nullable=False, server_default="EMAIL"),
        sa.Column("provider_user_id", sa.String(255), nullable=True),
        sa.Column("handle", sa.String(30), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("plan", plan, nullable=False, server_default="FREE"),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_handle", "users", ["handle"])

    biological_sex = sa.Enum("MALE", "FEMALE", name="biological_sex")
    activity_level = sa.Enum(
        "SEDENTARY", "LIGHT", "MODERATE", "ACTIVE", "VERY_ACTIVE", name="activity_level"
    )
    goal = sa.Enum(
        "EMAGRECIMENTO", "HIPERTROFIA", "MANUTENCAO", "PERFORMANCE", "RECOMPOSICAO", name="goal"
    )
    experience_level = sa.Enum(
        "INICIANTE", "INTERMEDIARIO", "AVANCADO", name="experience_level"
    )
    training_location = sa.Enum(
        "ACADEMIA_COMPLETA",
        "ACADEMIA_BASICA",
        "CASA_COM_EQUIPAMENTO",
        "CASA_SEM_EQUIPAMENTO",
        name="training_location",
    )
    training_style_preference = sa.Enum(
        "CURTO_INTENSO", "LONGO_VOLUMOSO", "IA_DECIDE", name="training_style_preference"
    )

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("biological_sex", biological_sex, nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("height_cm", sa.Float(), nullable=False),
        sa.Column("activity_level", activity_level, nullable=False),
        sa.Column("goal", goal, nullable=False),
        sa.Column("experience_level", experience_level, nullable=False),
        sa.Column("training_location", training_location, nullable=False),
        sa.Column(
            "training_style_preference",
            training_style_preference,
            nullable=False,
            server_default="IA_DECIDE",
        ),
        sa.Column(
            "available_days",
            sa.ARRAY(sa.String(10)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "dietary_restrictions",
            sa.ARRAY(sa.String(50)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("injuries_limitations", sa.Text(), nullable=True),
        sa.Column("preferred_advanced_technique", sa.String(50), nullable=True),
        sa.Column("trains_with_partner", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "partner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "weight_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_weight_logs_user_id", "weight_logs", ["user_id"])

    consent_type = sa.Enum("LGPD_HEALTH_DATA", "MEDICAL_DISCLAIMER", name="consent_type")

    op.create_table(
        "consent_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("consent_type", consent_type, nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])


def downgrade() -> None:
    op.drop_table("consent_records")
    op.drop_table("weight_logs")
    op.drop_table("user_profiles")
    op.drop_table("users")

    sa.Enum(name="consent_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="training_style_preference").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="training_location").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="experience_level").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="goal").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="activity_level").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="biological_sex").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="plan").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="auth_provider").drop(op.get_bind(), checkfirst=True)
