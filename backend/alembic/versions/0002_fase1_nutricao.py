"""Fase 1: nutricao manual - foods, meals, goals, water, measurements

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    food_source = sa.Enum("TACO", "OPEN_FOOD_FACTS", "CUSTOM", name="food_source")

    op.create_table(
        "foods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", food_source, nullable=False),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.Column("barcode", sa.String(30), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("brand", sa.String(150), nullable=True),
        sa.Column("kcal_per_100g", sa.Float(), nullable=False),
        sa.Column("protein_g_per_100g", sa.Float(), nullable=False),
        sa.Column("carbs_g_per_100g", sa.Float(), nullable=False),
        sa.Column("fat_g_per_100g", sa.Float(), nullable=False),
        sa.Column("fiber_g_per_100g", sa.Float(), nullable=True),
        sa.Column("sodium_mg_per_100g", sa.Float(), nullable=True),
        sa.Column("sugar_g_per_100g", sa.Float(), nullable=True),
        sa.Column("default_portion_g", sa.Float(), nullable=False, server_default="100"),
        sa.Column("default_portion_label", sa.String(50), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_food_source_external_id"),
    )
    op.create_index("ix_foods_external_id", "foods", ["external_id"])
    op.create_index("ix_foods_barcode", "foods", ["barcode"])
    op.create_index("ix_foods_name", "foods", ["name"])

    op.create_table(
        "meal_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "meal_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meal_category_id", sa.Integer(), sa.ForeignKey("meal_categories.id"), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_meal_logs_user_logged_at", "meal_logs", ["user_id", "logged_at"])

    op.create_table(
        "meal_log_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meal_log_id", sa.Integer(), sa.ForeignKey("meal_logs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("food_id", sa.Integer(), sa.ForeignKey("foods.id"), nullable=False),
        sa.Column("quantity_g", sa.Float(), nullable=False),
        sa.Column("kcal", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
        sa.Column("fiber_g", sa.Float(), nullable=True),
        sa.Column("sodium_mg", sa.Float(), nullable=True),
        sa.Column("sugar_g", sa.Float(), nullable=True),
    )

    op.create_table(
        "saved_meals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "saved_meal_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("saved_meal_id", sa.Integer(), sa.ForeignKey("saved_meals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("food_id", sa.Integer(), sa.ForeignKey("foods.id"), nullable=False),
        sa.Column("quantity_g", sa.Float(), nullable=False),
    )

    op.create_table(
        "favorite_foods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("food_id", sa.Integer(), sa.ForeignKey("foods.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "food_id", name="uq_favorite_user_food"),
    )

    goal_mode = sa.Enum("MANUAL", "AUTO", name="goal_mode")
    op.create_table(
        "calorie_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", goal_mode, nullable=False),
        sa.Column("kcal", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
        sa.Column("fiber_g", sa.Float(), nullable=True),
        sa.Column("sodium_mg", sa.Float(), nullable=True),
        sa.Column("sugar_g", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_calorie_goals_user_id", "calorie_goals", ["user_id"])

    op.create_table(
        "water_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount_ml", sa.Integer(), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_water_logs_user_logged_at", "water_logs", ["user_id", "logged_at"])

    measurement_type = sa.Enum(
        "WAIST", "HIP", "CHEST", "ARM_LEFT", "ARM_RIGHT", "THIGH_LEFT", "THIGH_RIGHT", "NECK",
        name="measurement_type",
    )
    op.create_table(
        "body_measurements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", measurement_type, nullable=False),
        sa.Column("value_cm", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "progress_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("photo_url", sa.String(500), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("progress_photos")
    op.drop_table("body_measurements")
    op.drop_table("water_logs")
    op.drop_table("calorie_goals")
    op.drop_table("favorite_foods")
    op.drop_table("saved_meal_items")
    op.drop_table("saved_meals")
    op.drop_table("meal_log_items")
    op.drop_table("meal_logs")
    op.drop_table("meal_categories")
    op.drop_table("foods")

    sa.Enum(name="measurement_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="goal_mode").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="food_source").drop(op.get_bind(), checkfirst=True)
