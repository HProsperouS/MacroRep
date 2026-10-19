"""set kind failure and drop

Revision ID: b4e7c1a9d2f8
Revises: a8d4c2e6b9f1
Create Date: 2026-10-19 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e7c1a9d2f8"
down_revision: str | None = "a8d4c2e6b9f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Only PostgreSQL has a native enum type to extend; elsewhere the column is a plain string.
    if op.get_bind().dialect.name != "postgresql":
        return
    # A new enum value can't be used in the transaction that adds it, so commit it on its own.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE set_kind ADD VALUE IF NOT EXISTS 'FAILURE'")
        op.execute("ALTER TYPE set_kind ADD VALUE IF NOT EXISTS 'DROP'")


def downgrade() -> None:
    # PostgreSQL can't drop a value from an enum, and rows may already use these
    # values; leaving them in place is harmless to the older code.
    pass
