"""photo food source

Food log entries can come from a meal-photo estimate the user confirmed.

Revision ID: e8b4f2a6c3d9
Revises: d7a3e5c1f8b2
Create Date: 2026-10-21 15:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8b4f2a6c3d9"
down_revision: str | None = "d7a3e5c1f8b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Only PostgreSQL has a native enum type to extend; elsewhere the column is a plain string.
    # A new enum value can't be used in the transaction that adds it, so commit it on its own.
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE food_source ADD VALUE IF NOT EXISTS 'PHOTO'")


def downgrade() -> None:
    # PostgreSQL can't drop an enum value; entries logged from photos become quick adds,
    # which the older code can read.
    op.execute("UPDATE food_entries SET source = 'QUICK_ADD' WHERE source = 'PHOTO'")
