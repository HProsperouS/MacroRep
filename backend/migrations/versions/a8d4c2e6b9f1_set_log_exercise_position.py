"""set log exercise position

Revision ID: a8d4c2e6b9f1
Revises: f7c3a8d1e2b4
Create Date: 2026-10-18 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8d4c2e6b9f1"
down_revision: str | None = "f7c3a8d1e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: sets logged before this column existed have no recorded
    # exercise order, and the workout history falls back to name order for them.
    op.add_column("workout_set_logs", sa.Column("exercise_position", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("workout_set_logs", "exercise_position")
