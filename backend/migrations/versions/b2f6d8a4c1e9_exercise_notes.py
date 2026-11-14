"""exercise notes

A user's own note on an exercise, one per user and exercise.

Revision ID: b2f6d8a4c1e9
Revises: c7e2a5f9b3d1
Create Date: 2026-11-13 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f6d8a4c1e9"
down_revision: str | None = "c7e2a5f9b3d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exercise_notes",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=40), nullable=False),
        sa.Column("exercise_id", sa.String(length=40), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_utc", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_exercise_notes_owner_exercise", "exercise_notes", ["owner_id", "exercise_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_exercise_notes_owner_exercise", table_name="exercise_notes")
    op.drop_table("exercise_notes")
