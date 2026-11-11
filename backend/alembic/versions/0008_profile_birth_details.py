"""Add learner date of birth and gender"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("date_of_birth", sa.String(10), nullable=False, server_default=""))
    op.add_column("profiles", sa.Column("gender", sa.String(40), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("profiles", "gender")
    op.drop_column("profiles", "date_of_birth")
