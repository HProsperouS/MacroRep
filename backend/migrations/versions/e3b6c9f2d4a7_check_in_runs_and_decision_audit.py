"""check-in runs and decision audit

Check-ins are generated in the background, so they gain RUNNING and FAILED
states and a user-facing failure reason. Proposals keep the changes exactly as
proposed next to the values the user decided on, and record when they were
decided.

Revision ID: e3b6c9f2d4a7
Revises: d1f4a7b2c8e5
Create Date: 2026-10-19 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3b6c9f2d4a7"
down_revision: str | None = "d1f4a7b2c8e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Only PostgreSQL has a native enum type to extend; elsewhere the column is a plain string.
    # A new enum value can't be used in the transaction that adds it, so commit it on its own.
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE check_in_status ADD VALUE IF NOT EXISTS 'RUNNING'")
            op.execute("ALTER TYPE check_in_status ADD VALUE IF NOT EXISTS 'FAILED'")

    op.add_column("coach_check_ins", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column("coach_proposals", sa.Column("decided_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column("coach_proposals", sa.Column("proposed_changes", sa.JSON(), nullable=True))
    # Earlier edits overwrote the proposed values, so the best record of them is what was stored.
    op.execute("UPDATE coach_proposals SET proposed_changes = changes")
    with op.batch_alter_table("coach_proposals") as batch:
        batch.alter_column("proposed_changes", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("coach_proposals") as batch:
        batch.drop_column("proposed_changes")
        batch.drop_column("decided_utc")
    op.drop_column("coach_check_ins", "failure_reason")
    # PostgreSQL can't drop enum values, and the old code can't read RUNNING or FAILED,
    # so those check-ins are kept as REVIEWED (they have no pending proposals).
    op.execute("UPDATE coach_check_ins SET status = 'REVIEWED' WHERE status IN ('RUNNING', 'FAILED')")
