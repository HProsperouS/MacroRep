"""usage events

Per-user limits on the paid AI calls (check-ins, Coach Chat questions, meal photos) were
counted in memory, so a restart reset them and each server counted on its own. Each call is
now a row, kept until it leaves its limit's window (app/shared/usage.py).

Revision ID: c7e2a5f9b3d1
Revises: b9c3e6a1d4f7
Create Date: 2026-11-10 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e2a5f9b3d1"
down_revision: str | None = "b9c3e6a1d4f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.String(length=40), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_usage_events_kind_owner_created",
        "usage_events",
        ["kind", "owner_id", "created_utc"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_usage_events_kind_owner_created", table_name="usage_events")
    op.drop_table("usage_events")
