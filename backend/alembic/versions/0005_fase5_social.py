"""Fase 5: social - amigos, privacidade, feed, bloqueio/denuncia, desafios

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    friend_request_status = sa.Enum("PENDING", "ACCEPTED", "DECLINED", name="friend_request_status")
    op.create_table(
        "friend_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requester_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("addressee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", friend_request_status, nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("requester_id", "addressee_id", name="uq_friend_request_pair"),
    )

    op.create_table(
        "blocked_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("blocked_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "blocked_user_id", name="uq_block_pair"),
    )

    report_target_type = sa.Enum("USER", "FEED_POST", name="report_target_type")
    report_status = sa.Enum("PENDING", "REVIEWED", name="report_status")
    op.create_table(
        "content_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", report_target_type, nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", report_status, nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    profile_visibility = sa.Enum("PRIVATE", "PUBLIC", name="profile_visibility")
    op.create_table(
        "user_privacy_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("profile_visibility", profile_visibility, nullable=False, server_default="PRIVATE"),
        sa.Column("share_workouts", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("share_meals", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("share_progress_photos", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    feed_post_type = sa.Enum("WORKOUT", "MEAL", "PROGRESS_PHOTO", name="feed_post_type")
    op.create_table(
        "feed_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_type", feed_post_type, nullable=False),
        sa.Column("reference_id", sa.Integer(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feed_posts_user_created", "feed_posts", ["user_id", "created_at"])

    op.create_table(
        "feed_reactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("feed_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("emoji", sa.String(8), nullable=False, server_default="👍"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("post_id", "user_id", name="uq_reaction_post_user"),
    )

    op.create_table(
        "feed_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("feed_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.String(280), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    challenge_metric = sa.Enum("WORKOUT_COUNT", "TOTAL_VOLUME", "STREAK_DAYS", name="challenge_metric")
    op.create_table(
        "challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("metric", challenge_metric, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "challenge_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("challenge_id", sa.Integer(), sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("challenge_id", "user_id", name="uq_challenge_participant"),
    )


def downgrade() -> None:
    op.drop_table("challenge_participants")
    op.drop_table("challenges")
    op.drop_table("feed_comments")
    op.drop_table("feed_reactions")
    op.drop_table("feed_posts")
    op.drop_table("user_privacy_settings")
    op.drop_table("content_reports")
    op.drop_table("blocked_users")
    op.drop_table("friend_requests")

    sa.Enum(name="challenge_metric").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="feed_post_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="profile_visibility").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="report_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="report_target_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="friend_request_status").drop(op.get_bind(), checkfirst=True)
