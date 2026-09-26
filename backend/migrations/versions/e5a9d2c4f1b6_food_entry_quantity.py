"""food entry food link and quantity

Revision ID: e5a9d2c4f1b6
Revises: c3b8e1f7a2d9
Create Date: 2026-09-26 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a9d2c4f1b6"
down_revision: str | None = "c3b8e1f7a2d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


quantity_unit_enum = sa.Enum("serving", "g", name="quantity_unit")


def upgrade() -> None:
    # All nullable: entries logged before this migration keep no food link and
    # stay editable value by value, exactly like quick adds.
    quantity_unit_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("food_entries", sa.Column("food_id", sa.String(length=40), nullable=True))
    op.add_column("food_entries", sa.Column("quantity", sa.Numeric(precision=8, scale=2), nullable=True))
    op.add_column("food_entries", sa.Column("quantity_unit", quantity_unit_enum, nullable=True))
    op.create_foreign_key(
        "fk_food_entries_food_id_foods", "food_entries", "foods", ["food_id"], ["id"], ondelete="SET NULL"
    )
    # Postgres doesn't index foreign keys on its own; without this, deleting a
    # food would scan every food entry to null out its references.
    op.create_index("ix_food_entries_food", "food_entries", ["food_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_food_entries_food", table_name="food_entries")
    op.drop_constraint("fk_food_entries_food_id_foods", "food_entries", type_="foreignkey")
    op.drop_column("food_entries", "quantity_unit")
    op.drop_column("food_entries", "quantity")
    op.drop_column("food_entries", "food_id")
    quantity_unit_enum.drop(op.get_bind(), checkfirst=True)
