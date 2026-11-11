"""Indexes for recording lookups

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_recordings_user_id", "recordings", ["user_id"])
    op.create_index("ix_recordings_lesson_id", "recordings", ["lesson_id"])
    op.create_index("ix_evaluations_status", "evaluations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_evaluations_status", table_name="evaluations")
    op.drop_index("ix_recordings_lesson_id", table_name="recordings")
    op.drop_index("ix_recordings_user_id", table_name="recordings")
