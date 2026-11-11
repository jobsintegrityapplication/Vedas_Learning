"""Store approved profile-specific Padapāṭha and phonetic references."""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "recitation_text_variants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile", sa.String(20), nullable=False),
        sa.Column("mantra_reference", sa.String(32), nullable=False),
        sa.Column("samhita_form", sa.Text(), nullable=False),
        sa.Column("padapatha_form", sa.Text(), nullable=False),
        sa.Column("padapatha_tokens", _json_type(), nullable=False),
        sa.Column("phonetic_metadata", _json_type(), nullable=False),
        sa.Column("source_provenance", _json_type(), nullable=False),
        sa.Column("rights_status", sa.String(40), server_default="unknown", nullable=False),
        sa.Column("validation_status", sa.String(40), server_default="pending", nullable=False),
        sa.Column("reviewer", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile", "mantra_reference", name="uq_recitation_text_variant_profile_reference"),
    )
    op.create_index("ix_recitation_text_variants_profile", "recitation_text_variants", ["profile"])
    op.create_index("ix_recitation_text_variants_mantra_reference", "recitation_text_variants", ["mantra_reference"])


def downgrade() -> None:
    op.drop_index("ix_recitation_text_variants_mantra_reference", table_name="recitation_text_variants")
    op.drop_index("ix_recitation_text_variants_profile", table_name="recitation_text_variants")
    op.drop_table("recitation_text_variants")
