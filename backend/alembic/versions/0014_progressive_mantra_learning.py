"""Persist per-profile mantra learning progress and attempts."""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "progressive_mantra_progress",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile", sa.String(20), nullable=False), sa.Column("mantra_reference", sa.String(32), nullable=False),
        sa.Column("unlocked_word_order", sa.Integer(), server_default="1", nullable=False),
        sa.Column("current_word_order", sa.Integer(), server_default="1", nullable=False),
        sa.Column("completed_word_orders", _json_type(), server_default="[]", nullable=False),
        sa.Column("bookmarked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("combined_passed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "profile", "mantra_reference", name="uq_progressive_user_profile_mantra"),
    )
    op.create_index("ix_progressive_mantra_progress_user_id", "progressive_mantra_progress", ["user_id"])
    op.create_table(
        "progressive_mantra_attempts",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile", sa.String(20), nullable=False), sa.Column("mantra_reference", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False), sa.Column("word_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False), sa.Column("content_type", sa.String(80), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False), sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("evaluation_status", sa.String(40), server_default="unavailable", nullable=False),
        sa.Column("report", _json_type(), nullable=True), sa.Column("passed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_progressive_mantra_attempts_user_id", "progressive_mantra_attempts", ["user_id"])
    op.create_index("ix_progressive_mantra_attempts_mantra_reference", "progressive_mantra_attempts", ["mantra_reference"])


def downgrade() -> None:
    op.drop_index("ix_progressive_mantra_attempts_mantra_reference", table_name="progressive_mantra_attempts")
    op.drop_index("ix_progressive_mantra_attempts_user_id", table_name="progressive_mantra_attempts")
    op.drop_table("progressive_mantra_attempts")
    op.drop_index("ix_progressive_mantra_progress_user_id", table_name="progressive_mantra_progress")
    op.drop_table("progressive_mantra_progress")
