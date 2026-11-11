"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="learner"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("name", sa.String(200), server_default=""),
        sa.Column("age", sa.String(20), server_default=""),
        sa.Column("phone", sa.String(40), server_default=""),
        sa.Column("email", sa.String(320), server_default=""),
        sa.Column("rashi", sa.String(80), server_default=""),
        sa.Column("nakshatra", sa.String(80), server_default=""),
        sa.Column("profession", sa.String(120), server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "email_otps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "purpose", name="uq_otp_user_purpose"),
    )

    op.create_table(
        "scriptures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "chapters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scripture_id", sa.Uuid(), sa.ForeignKey("scriptures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("scripture_id", "sort_order", name="uq_chapter_order"),
    )

    op.create_table(
        "lessons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("scripture_id", sa.Uuid(), sa.ForeignKey("scriptures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("canonical_reference", sa.String(200), nullable=False),
        sa.Column("sanskrit_text", sa.Text(), nullable=False),
        sa.Column("transliteration", sa.Text(), server_default=""),
        sa.Column("meaning", sa.Text(), nullable=False),
        sa.Column("daily_application", sa.Text(), server_default=""),
        sa.Column("word_meanings", sa.JSON(), nullable=True),
        sa.Column("reference_audio_key", sa.String(500), nullable=True),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("source", sa.String(40), nullable=False, server_default="guru_provided"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "lesson_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("note", sa.Text(), server_default=""),
        sa.Column("previous_sanskrit", sa.Text(), nullable=True),
        sa.Column("previous_meaning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "recordings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(80), server_default="audio/mp4"),
        sa.Column("original_filename", sa.String(200), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("recording_id", sa.Uuid(), sa.ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("engine_id", sa.String(80), server_default="none"),
        sa.Column("engine_version", sa.String(40), server_default="0"),
        sa.Column("word_accuracy_status", sa.String(40), server_default="unavailable"),
        sa.Column("pronunciation_status", sa.String(40), server_default="unavailable"),
        sa.Column("svara_status", sa.String(40), server_default="unavailable"),
        sa.Column("alignment", sa.JSON(), nullable=True),
        sa.Column("message", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "progress",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_recording_id", sa.Uuid(), sa.ForeignKey("recordings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("last_practiced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_progress_user_lesson"),
    )


def downgrade() -> None:
    op.drop_table("progress")
    op.drop_table("evaluations")
    op.drop_table("recordings")
    op.drop_table("lesson_audits")
    op.drop_table("lessons")
    op.drop_table("chapters")
    op.drop_table("scriptures")
    op.drop_table("email_otps")
    op.drop_table("profiles")
    op.drop_table("users")
