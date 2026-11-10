"""food entry detail

A saved food's entry can say which version of the food it was ("roasted, less
rice"), since its name always comes from the food. Display only.

Revision ID: b9c3e6a1d4f7
Revises: a8e4c2f6d0b9
Create Date: 2026-11-10 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9c3e6a1d4f7"
down_revision: str | None = "a8e4c2f6d0b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: existing entries simply have no detail.
    op.add_column("food_entries", sa.Column("detail", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("food_entries", "detail")
