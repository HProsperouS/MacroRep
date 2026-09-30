"""profile timezone

Revision ID: f7c3a8d1e2b4
Revises: e5a9d2c4f1b6
Create Date: 2026-09-30 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7c3a8d1e2b4"
down_revision: str | None = "e5a9d2c4f1b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing profiles start on UTC, the behaviour they had before; the
    # browser replaces it with the real zone on the user's next visit.
    op.add_column(
        "profiles",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
    )


def downgrade() -> None:
    op.drop_column("profiles", "timezone")
