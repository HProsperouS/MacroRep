"""profile birth date, sex and activity level

What estimating starting targets needs (Mifflin-St Jeor and an activity factor).

Revision ID: a2d6f8c4e1b7
Revises: f9c5a3b7d1e4
Create Date: 2026-10-21 20:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2d6f8c4e1b7"
down_revision: str | None = "f9c5a3b7d1e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


sex_enum = sa.Enum("MALE", "FEMALE", name="profile_sex")
activity_level_enum = sa.Enum("SEDENTARY", "LIGHT", "MODERATE", "VERY", name="activity_level")


def upgrade() -> None:
    # Nullable: a profile exists from the first page load, before the sign-up guide asks
    # for these. Saving a profile requires them. `op.add_column` doesn't create an enum's
    # Postgres type, so each is created first.
    sex_enum.create(op.get_bind(), checkfirst=True)
    activity_level_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("profiles", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("profiles", sa.Column("sex", sex_enum, nullable=True))
    op.add_column("profiles", sa.Column("activity_level", activity_level_enum, nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "activity_level")
    op.drop_column("profiles", "sex")
    op.drop_column("profiles", "date_of_birth")
    activity_level_enum.drop(op.get_bind(), checkfirst=True)
    sex_enum.drop(op.get_bind(), checkfirst=True)
