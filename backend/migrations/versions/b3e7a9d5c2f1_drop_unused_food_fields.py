"""drop unused food fields

A food's brand, fibre, sugar and sodium were stored but never used: nothing logged,
totalled, targeted or showed them. Foods now hold what every entry does: a name, a
serving, calories and macros.

Revision ID: b3e7a9d5c2f1
Revises: a2d6f8c4e1b7
Create Date: 2026-10-21 23:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3e7a9d5c2f1"
down_revision: str | None = "a2d6f8c4e1b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("foods", "sodium_mg")
    op.drop_column("foods", "sugar_g")
    op.drop_column("foods", "fibre_g")
    op.drop_column("foods", "brand")


def downgrade() -> None:
    op.add_column("foods", sa.Column("brand", sa.String(length=255), nullable=True))
    op.add_column("foods", sa.Column("fibre_g", sa.Numeric(precision=6, scale=1), nullable=True))
    op.add_column("foods", sa.Column("sugar_g", sa.Numeric(precision=6, scale=1), nullable=True))
    op.add_column("foods", sa.Column("sodium_mg", sa.Numeric(precision=7, scale=1), nullable=True))
