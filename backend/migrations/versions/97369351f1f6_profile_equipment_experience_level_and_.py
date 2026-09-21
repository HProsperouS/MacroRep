"""profile equipment experience level and set rpe

Revision ID: 97369351f1f6
Revises: a1f4c9e2b7d3
Create Date: 2026-09-20 22:08:50.602939

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "97369351f1f6"
down_revision: str | None = "a1f4c9e2b7d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


experience_level_enum = sa.Enum("BEGINNER", "INTERMEDIATE", "ADVANCED", name="experience_level")


def upgrade() -> None:
    # server_default backfills existing rows so these NOT NULL columns can be
    # added without failing on any profile created before this migration;
    # the ORM model has no column default of its own, only a Python-side one
    # applied to newly-constructed rows (see app/profile/service.py).
    #
    # `op.add_column` does not create the enum's backing Postgres type on its
    # own (unlike `op.create_table`, which creates enum types inline) — it
    # must be created explicitly first.
    experience_level_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "profiles",
        sa.Column("experience_level", experience_level_enum, nullable=False, server_default="BEGINNER"),
    )
    op.add_column(
        "profiles", sa.Column("equipment", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
    )
    op.add_column("workout_set_logs", sa.Column("rpe", sa.Numeric(precision=3, scale=1), nullable=True))


def downgrade() -> None:
    op.drop_column("workout_set_logs", "rpe")
    op.drop_column("profiles", "equipment")
    op.drop_column("profiles", "experience_level")
    experience_level_enum.drop(op.get_bind(), checkfirst=True)
