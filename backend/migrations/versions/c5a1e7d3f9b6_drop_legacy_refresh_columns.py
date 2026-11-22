"""drop legacy refresh columns

``users.refresh_token_hash`` and ``refresh_expires_at`` held the one refresh token per user
from before ``user_sessions`` (``b4f0d6c2e8a5``), which copied them over. Nothing reads them
any more. They were going to be kept for one release so old tasks could run during the
deploy, but nothing had been deployed yet, so they are dropped straight away.

Revision ID: c5a1e7d3f9b6
Revises: b4f0d6c2e8a5
Create Date: 2026-11-22 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5a1e7d3f9b6"
down_revision: str | None = "b4f0d6c2e8a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("users", "refresh_expires_at")
    op.drop_column("users", "refresh_token_hash")


def downgrade() -> None:
    # Empty columns: downgrading past b4f0d6c2e8a5 refills them from user_sessions.
    op.add_column("users", sa.Column("refresh_token_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True))
