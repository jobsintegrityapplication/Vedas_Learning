"""refresh tokens and audio metadata

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.add_column("recordings", sa.Column("kind", sa.String(40), nullable=False, server_default="learner"))
    op.add_column("recordings", sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("lessons", sa.Column("reference_audio_content_type", sa.String(80), nullable=True))
    op.add_column("lessons", sa.Column("reference_audio_byte_size", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("lessons", sa.Column("reference_audio_filename", sa.String(200), nullable=True))
    with op.batch_alter_table("chapters") as batch:
        batch.drop_constraint("uq_chapter_order", type_="unique")


def downgrade() -> None:
    with op.batch_alter_table("chapters") as batch:
        batch.create_unique_constraint("uq_chapter_order", ["scripture_id", "sort_order"])
    op.drop_column("lessons", "reference_audio_filename")
    op.drop_column("lessons", "reference_audio_byte_size")
    op.drop_column("lessons", "reference_audio_content_type")
    op.drop_column("recordings", "byte_size")
    op.drop_column("recordings", "kind")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
