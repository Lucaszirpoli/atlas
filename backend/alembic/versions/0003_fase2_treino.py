"""Fase 2: treino manual - exercises, routines, workout sessions

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    muscle_group = sa.Enum(
        "CHEST", "BACK", "SHOULDERS", "BICEPS", "TRICEPS", "QUADS", "HAMSTRINGS",
        "GLUTES", "CALVES", "ABS", "FOREARMS", "TRAPS", "FULL_BODY", "CARDIO",
        name="muscle_group",
    )
    equipment = sa.Enum(
        "BARBELL", "DUMBBELL", "MACHINE", "CABLE", "BODYWEIGHT", "KETTLEBELL",
        "BAND", "SMITH_MACHINE", "OTHER", name="equipment",
    )
    difficulty = sa.Enum("BEGINNER", "INTERMEDIATE", "ADVANCED", name="difficulty")

    op.create_table(
        "exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("primary_muscle_group", muscle_group, nullable=False),
        sa.Column("secondary_muscle_groups", sa.ARRAY(sa.String(20)), nullable=False, server_default="{}"),
        sa.Column("equipment", equipment, nullable=False),
        sa.Column("difficulty", difficulty, nullable=False),
        sa.Column("execution_text", sa.Text(), nullable=True),
        sa.Column("video_url", sa.String(500), nullable=True),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_exercises_name", "exercises", ["name"])

    op.create_table(
        "routines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_routines_user_id", "routines", ["user_id"])

    op.create_table(
        "routine_exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("routine_id", sa.Integer(), sa.ForeignKey("routines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_sets", sa.Integer(), nullable=False),
        sa.Column("target_reps_min", sa.Integer(), nullable=False),
        sa.Column("target_reps_max", sa.Integer(), nullable=True),
        sa.Column("rest_seconds", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "workout_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("routine_id", sa.Integer(), sa.ForeignKey("routines.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workout_sessions_user_routine", "workout_sessions", ["user_id", "routine_id"])

    set_type = sa.Enum(
        "WARMUP", "STRAIGHT", "DROP_SET", "REST_PAUSE", "MYO_REPS", "CLUSTER_SET",
        "TO_FAILURE", "TECHNICAL_FAILURE", "TEMPO", "ECCENTRIC_EMPHASIS",
        "PRE_EXHAUSTION", "SUPERSET", "BISET", "TRISET", "CIRCUIT",
        name="set_type",
    )
    op.create_table(
        "workout_set_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("exercise_sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("set_type", set_type, nullable=False, server_default="STRAIGHT"),
        sa.Column("rpe", sa.Float(), nullable=True),
        sa.Column("rir", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workout_set_logs_session_exercise", "workout_set_logs", ["session_id", "exercise_id"])


def downgrade() -> None:
    op.drop_table("workout_set_logs")
    op.drop_table("workout_sessions")
    op.drop_table("routine_exercises")
    op.drop_table("routines")
    op.drop_table("exercises")

    sa.Enum(name="set_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="difficulty").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="equipment").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="muscle_group").drop(op.get_bind(), checkfirst=True)
