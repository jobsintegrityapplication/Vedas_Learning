"""Store optional gotra and preferred content language on learner profiles."""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("gotra", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("profiles", sa.Column("preferred_language", sa.String(length=5), nullable=False, server_default="en"))


def downgrade() -> None:
    op.drop_column("profiles", "preferred_language")
    op.drop_column("profiles", "gotra")
