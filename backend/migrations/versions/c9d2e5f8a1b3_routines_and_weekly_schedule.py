"""routines and weekly schedule

Each weekday used to own its plan (``workout_plan_entries.day_of_week``). Plans become
reusable routines, and the new ``workout_schedule_days`` table says which routine a
weekday uses. Existing plans keep their exercises and stay scheduled on the same day.

Revision ID: c9d2e5f8a1b3
Revises: b4e7c1a9d2f8
Create Date: 2026-10-19 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d2e5f8a1b3"
down_revision: str | None = "b4e7c1a9d2f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_schedule_days",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=40), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("routine_id", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["routine_id"], ["workout_plan_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_workout_schedule_owner_day", "workout_schedule_days", ["owner_id", "day_of_week"], unique=True
    )
    # Every existing plan was for exactly one weekday, so it becomes a routine scheduled on that day.
    # The plan's own id doubles as the schedule row's id, which is unique and needs no generator.
    op.execute(
        "INSERT INTO workout_schedule_days (id, owner_id, day_of_week, routine_id) "
        "SELECT id, owner_id, day_of_week, id FROM workout_plan_entries"
    )

    op.drop_index("uq_workout_plan_owner_day", table_name="workout_plan_entries")
    with op.batch_alter_table("workout_plan_entries") as batch:
        batch.drop_column("day_of_week")
    op.create_index("ix_workout_plan_entries_owner", "workout_plan_entries", ["owner_id"])


def downgrade() -> None:
    # A routine can be scheduled on several days, or none, which a single day_of_week
    # column can't hold; restoring it would silently lose routines.
    raise NotImplementedError("Routines can't be turned back into per-weekday plans without losing data")
