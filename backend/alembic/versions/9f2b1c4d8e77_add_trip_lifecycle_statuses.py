"""add draft, creating and created trip lifecycle statuses"""
from typing import Sequence, Union

from alembic import op


revision: str = "9f2b1c4d8e77"
down_revision: Union[str, Sequence[str], None] = "7c3e4f8a2d11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL uses a native enum for TripStatus. SQLite stores SQLAlchemy
    # enums as strings, so there is nothing to alter for local SQLite setups.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in ("DRAFT", "CREATING", "CREATED"):
            op.execute(f"ALTER TYPE tripstatus ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely without rebuilding the
    # type; leaving the values is the safe downgrade behavior.
    pass
