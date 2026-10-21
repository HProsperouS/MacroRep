"""profile onboarded

When the user finished the sign-up guide.

Revision ID: f9c5a3b7d1e4
Revises: e8b4f2a6c3d9
Create Date: 2026-10-21 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9c5a3b7d1e4"
down_revision: str | None = "e8b4f2a6c3d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("onboarded_utc", sa.DateTime(timezone=True), nullable=True))
    # Profiles from before the guide were set up on the Profile page: don't send them through it.
    op.execute("UPDATE profiles SET onboarded_utc = created_utc")


def downgrade() -> None:
    op.drop_column("profiles", "onboarded_utc")
