"""check-in idempotency key and input snapshot

Revision ID: c3b8e1f7a2d9
Revises: 97369351f1f6
Create Date: 2026-09-25 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3b8e1f7a2d9"
down_revision: str | None = "97369351f1f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Both nullable: check-ins created before this migration (and the demo
    # seed) have no key or snapshot, and NULL keys never collide in the index.
    op.add_column("coach_check_ins", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.add_column("coach_check_ins", sa.Column("input_snapshot", sa.JSON(), nullable=True))
    op.create_index(
        "uq_coach_check_ins_owner_idempotency_key",
        "coach_check_ins",
        ["owner_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_coach_check_ins_owner_idempotency_key", table_name="coach_check_ins")
    op.drop_column("coach_check_ins", "input_snapshot")
    op.drop_column("coach_check_ins", "idempotency_key")
