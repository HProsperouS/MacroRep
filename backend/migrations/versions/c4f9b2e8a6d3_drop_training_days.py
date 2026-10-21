"""drop training days per week

The weekly schedule already says which days the user trains, and nothing read
this number.

Revision ID: c4f9b2e8a6d3
Revises: b3e7a9d5c2f1
Create Date: 2026-10-22 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f9b2e8a6d3"
down_revision: str | None = "b3e7a9d5c2f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("profiles", "training_days_per_week")


def downgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("training_days_per_week", sa.Integer(), nullable=False, server_default="3"),
    )
