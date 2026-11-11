"""Add line-indexed recordings and learner line completion history."""
from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("recordings", sa.Column("line_index", sa.Integer(), server_default="0", nullable=False))
    op.create_table(
        "lesson_line_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=False),
        sa.Column("line_index", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "lesson_id", "line_index", name="uq_line_progress_user_lesson_line"),
    )
    op.create_index("ix_lesson_line_progress_user_id", "lesson_line_progress", ["user_id"])
    op.create_index("ix_lesson_line_progress_lesson_id", "lesson_line_progress", ["lesson_id"])

def downgrade() -> None:
    op.drop_index("ix_lesson_line_progress_lesson_id", table_name="lesson_line_progress")
    op.drop_index("ix_lesson_line_progress_user_id", table_name="lesson_line_progress")
    op.drop_table("lesson_line_progress")
    op.drop_column("recordings", "line_index")
