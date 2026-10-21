"""chat revisions

Coach Chat can revise a pending proposal at the user's request: the proposal keeps the
versions it replaced, and each coach message says whether it answered, asked a clarifying
question or reported a revision.

Revision ID: d7a3e5c1f8b2
Revises: c4f8a2d6e9b1
Create Date: 2026-10-21 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7a3e5c1f8b2"
down_revision: str | None = "c4f8a2d6e9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "coach_proposals",
        sa.Column("revisions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    # The default only fills existing rows; new ones get theirs from the model.
    with op.batch_alter_table("coach_proposals") as batch:
        batch.alter_column("revisions", existing_type=sa.JSON(), server_default=None)
    op.add_column(
        "coach_messages",
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="answer"),
    )


def downgrade() -> None:
    op.drop_column("coach_messages", "kind")
    op.drop_column("coach_proposals", "revisions")
