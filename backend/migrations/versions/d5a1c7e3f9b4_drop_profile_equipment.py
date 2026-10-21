"""drop profile equipment

The equipment a user has was asked for but never used: the coach adjusts a routine's own
exercises and never swaps one, and one "machine" box couldn't say which machines a gym
has. Exercises keep the equipment they need.

Revision ID: d5a1c7e3f9b4
Revises: c4f9b2e8a6d3
Create Date: 2026-10-22 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5a1c7e3f9b4"
down_revision: str | None = "c4f9b2e8a6d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("profiles", "equipment")


def downgrade() -> None:
    op.add_column(
        "profiles", sa.Column("equipment", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
    )
