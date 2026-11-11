"""Separate Kanchi/Sringeri reference assets and learner recordings."""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recordings", sa.Column("recitation_profile", sa.String(20), server_default="Kanchi", nullable=False))
    op.add_column("recordings", sa.Column("mantra_reference", sa.String(32), nullable=True))
    op.create_index("ix_recordings_mantra_reference", "recordings", ["mantra_reference"])
    op.create_table(
        "recitation_reference_audio",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile", sa.String(20), nullable=False),
        sa.Column("mantra_reference", sa.String(32), nullable=False),
        sa.Column("asset_kind", sa.String(20), nullable=False),
        sa.Column("word_order", sa.Integer(), nullable=True),
        sa.Column("start_ms", sa.Integer(), nullable=True),
        sa.Column("end_ms", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("source_title", sa.String(300), nullable=False),
        sa.Column("speaker_attribution", sa.String(300), nullable=False),
        sa.Column("source_attribution", sa.String(500), nullable=False),
        sa.Column("rights_status", sa.String(40), server_default="unknown", nullable=False),
        sa.Column("rights_notes", sa.Text(), server_default="", nullable=False),
        sa.Column("validation_status", sa.String(40), server_default="pending", nullable=False),
        sa.Column("validation_notes", sa.Text(), server_default="", nullable=False),
        sa.Column("content_type", sa.String(80), nullable=False),
        sa.Column("original_filename", sa.String(200), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=True),
        sa.Column("container", sa.String(20), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile", "mantra_reference", "asset_kind", "word_order", name="uq_reference_audio_profile_mantra_kind_word"),
    )
    op.create_index("ix_recitation_reference_audio_profile", "recitation_reference_audio", ["profile"])
    op.create_index("ix_recitation_reference_audio_mantra_reference", "recitation_reference_audio", ["mantra_reference"])


def downgrade() -> None:
    op.drop_index("ix_recitation_reference_audio_mantra_reference", table_name="recitation_reference_audio")
    op.drop_index("ix_recitation_reference_audio_profile", table_name="recitation_reference_audio")
    op.drop_table("recitation_reference_audio")
    op.drop_index("ix_recordings_mantra_reference", table_name="recordings")
    op.drop_column("recordings", "mantra_reference")
    op.drop_column("recordings", "recitation_profile")
