"""clear placeholder chat

Before Coach Chat answered from the check-in, every question got the same canned reply.
Those exchanges would now be shown as a real conversation and sent to the model as one, so
they're removed. Nothing else was ever stored in coach_messages.

Revision ID: c4f8a2d6e9b1
Revises: e3b6c9f2d4a7
Create Date: 2026-10-21 09:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f8a2d6e9b1"
down_revision: str | None = "e3b6c9f2d4a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM coach_messages")


def downgrade() -> None:
    # The canned replies carried nothing worth restoring.
    pass
