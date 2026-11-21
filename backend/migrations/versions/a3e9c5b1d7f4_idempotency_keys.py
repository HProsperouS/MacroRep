"""idempotency keys on workouts and food entries

A retried finish or add (after a lost answer) sends the same Idempotency-Key, which is
stored with the row under a unique (owner, key) index so the retry can't create a
duplicate. Nullable: rows from before, and requests without the header, have none.

Revision ID: a3e9c5b1d7f4
Revises: f2d8b4a6c0e3
Create Date: 2026-11-21 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3e9c5b1d7f4"
down_revision: str | None = "f2d8b4a6c0e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workout_sessions", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.create_index(
        "uq_workout_sessions_owner_idempotency_key",
        "workout_sessions",
        ["owner_id", "idempotency_key"],
        unique=True,
    )
    op.add_column("food_entries", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.create_index(
        "uq_food_entries_owner_idempotency_key", "food_entries", ["owner_id", "idempotency_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_food_entries_owner_idempotency_key", table_name="food_entries")
    op.drop_column("food_entries", "idempotency_key")
    op.drop_index("uq_workout_sessions_owner_idempotency_key", table_name="workout_sessions")
    op.drop_column("workout_sessions", "idempotency_key")
