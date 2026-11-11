"""Username, phone, and signup completion

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(80), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("signup_completed", sa.Boolean(), nullable=False, server_default=sa.false()))
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("UPDATE users SET signup_completed = true WHERE is_verified = true")
        op.execute(
            "UPDATE users SET username = split_part(email, '@', 1) || '-' || substring(id::text, 1, 8) "
            "WHERE username IS NULL"
        )
        op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)
    else:
        with op.batch_alter_table("users") as batch:
            batch.alter_column("password_hash", existing_type=sa.String(255), nullable=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "signup_completed")
    op.drop_column("users", "phone")
    op.drop_column("users", "username")
