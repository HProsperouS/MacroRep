"""drop routine week label and estimated minutes

A routine repeats every week, so its "Week 1" label never changed and said nothing. Its
time is now worked out from its sets and rests instead of being typed in.

Revision ID: f7d3b9a5c1e8
Revises: e6c2a8f4b1d7
Create Date: 2026-10-22 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7d3b9a5c1e8"
down_revision: str | None = "e6c2a8f4b1d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("workout_plan_entries", "week_label")
    op.drop_column("workout_plan_entries", "estimated_minutes")


def downgrade() -> None:
    op.add_column(
        "workout_plan_entries",
        sa.Column("estimated_minutes", sa.Integer(), nullable=False, server_default=sa.text("45")),
    )
    op.add_column(
        "workout_plan_entries",
        sa.Column("week_label", sa.String(length=64), nullable=False, server_default="Week 1"),
    )
