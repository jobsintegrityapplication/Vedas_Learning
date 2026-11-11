"""Separate Guru audio, evaluation evidence report, recording inspection

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recordings", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("recordings", sa.Column("sample_rate", sa.Integer(), nullable=True))
    op.add_column("recordings", sa.Column("container", sa.String(20), nullable=True))
    op.add_column("evaluations", sa.Column("report", sa.JSON(), nullable=True))
    op.add_column("evaluations", sa.Column("hypothesis_tokens", sa.JSON(), nullable=True))
    op.create_table(
        "guru_reference_audio",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(80), server_default="audio/wav"),
        sa.Column("original_filename", sa.String(200), server_default=""),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=True),
        sa.Column("container", sa.String(20), nullable=True),
        sa.Column("uploaded_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("guru_reference_audio")
    op.drop_column("evaluations", "hypothesis_tokens")
    op.drop_column("evaluations", "report")
    op.drop_column("recordings", "container")
    op.drop_column("recordings", "sample_rate")
    op.drop_column("recordings", "duration_ms")
