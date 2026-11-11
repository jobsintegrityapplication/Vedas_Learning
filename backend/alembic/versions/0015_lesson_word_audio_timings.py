"""Store reviewed word boundaries within Guru lesson audio."""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    word_timings = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.add_column("lessons", sa.Column("word_audio_timings", word_timings, nullable=True))


def downgrade() -> None:
    op.drop_column("lessons", "word_audio_timings")
