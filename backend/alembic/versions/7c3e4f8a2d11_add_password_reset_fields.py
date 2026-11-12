"""add password reset fields

Revision ID: 7c3e4f8a2d11
Revises: 21e19e7036da
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "7c3e4f8a2d11"
down_revision: Union[str, Sequence[str], None] = "21e19e7036da"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_reset_token_hash", sa.String(), nullable=True))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_password_reset_token_hash", "users", ["password_reset_token_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_password_reset_token_hash", table_name="users")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_token_hash")
