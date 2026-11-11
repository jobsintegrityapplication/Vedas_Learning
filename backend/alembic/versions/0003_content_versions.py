"""Guru content versioning, shloka metadata, translations, publish audit

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lessons", sa.Column("shloka_number", sa.String(80), nullable=False, server_default=""))
    op.add_column("lessons", sa.Column("translation", sa.Text(), nullable=False, server_default=""))
    op.add_column("lessons", sa.Column("translations", sa.JSON(), nullable=True))
    op.add_column("lessons", sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("lessons", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("lessons", sa.Column("published_by_id", sa.Uuid(), nullable=True))
    with op.batch_alter_table("lessons") as batch:
        batch.create_foreign_key("fk_lessons_published_by_id", "users", ["published_by_id"], ["id"], ondelete="SET NULL")
        batch.alter_column("is_published", server_default=sa.false())

    op.add_column("lesson_audits", sa.Column("version_number", sa.Integer(), nullable=True))
    op.add_column("lesson_audits", sa.Column("snapshot", sa.JSON(), nullable=True))

    op.create_table(
        "lesson_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), server_default=""),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("shloka_number", sa.String(80), nullable=False, server_default=""),
        sa.Column("canonical_reference", sa.String(200), nullable=False),
        sa.Column("sanskrit_text", sa.Text(), nullable=False),
        sa.Column("transliteration", sa.Text(), server_default=""),
        sa.Column("meaning", sa.Text(), nullable=False),
        sa.Column("translation", sa.Text(), server_default=""),
        sa.Column("translations", sa.JSON(), nullable=True),
        sa.Column("word_meanings", sa.JSON(), nullable=True),
        sa.Column("daily_application", sa.Text(), server_default=""),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("reference_audio_key", sa.String(500), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lesson_versions_lesson_id", "lesson_versions", ["lesson_id"])
    op.create_index("uq_lesson_version", "lesson_versions", ["lesson_id", "version_number"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_lesson_version", table_name="lesson_versions")
    op.drop_index("ix_lesson_versions_lesson_id", table_name="lesson_versions")
    op.drop_table("lesson_versions")
    op.drop_column("lesson_audits", "snapshot")
    op.drop_column("lesson_audits", "version_number")
    op.drop_column("lessons", "published_by_id")
    op.drop_column("lessons", "published_at")
    op.drop_column("lessons", "version_number")
    op.drop_column("lessons", "translations")
    op.drop_column("lessons", "translation")
    op.drop_column("lessons", "shloka_number")
    op.alter_column("lessons", "is_published", server_default=sa.true())
