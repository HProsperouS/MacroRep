"""versioned nutrition targets

The four target columns on ``profiles`` were overwritten on every change, so a
past day could only be judged against today's target. Targets move to
``nutrition_targets``, one row per version with the day it took effect. Each
profile's current targets become its version 1.

Revision ID: d1f4a7b2c8e5
Revises: c9d2e5f8a1b3
Create Date: 2026-10-19 15:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1f4a7b2c8e5"
down_revision: str | None = "c9d2e5f8a1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TARGET_COLUMNS = ("target_calories", "target_protein_g", "target_carbs_g", "target_fat_g")


def upgrade() -> None:
    op.create_table(
        "nutrition_targets",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("calories", sa.Integer(), nullable=False),
        sa.Column("protein_g", sa.Numeric(precision=6, scale=1), nullable=False),
        sa.Column("carbs_g", sa.Numeric(precision=6, scale=1), nullable=False),
        sa.Column("fat_g", sa.Numeric(precision=6, scale=1), nullable=False),
        sa.Column(
            "source", sa.Enum("INITIAL", "MANUAL", "CHECK_IN", name="nutrition_target_source"), nullable=False
        ),
        sa.Column("proposal_id", sa.String(length=40), nullable=True),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_utc", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proposal_id"], ["coach_proposals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_nutrition_targets_owner_version", "nutrition_targets", ["owner_id", "version"], unique=True
    )
    # Version 1 takes effect on the day the profile was created, in the user's own timezone:
    # it is the earliest target known, and a day before the first version is judged against
    # it anyway. Computed here rather than in SQL, which has no portable "local date of a
    # timestamp" (SQLite's CAST(... AS DATE) yields a number). The profile's user id doubles
    # as the row id, which is unique per profile and needs no generator.
    bind = op.get_bind()
    profiles = bind.execute(
        sa.text(
            "SELECT user_id, timezone, created_utc, target_calories, target_protein_g, "
            "target_carbs_g, target_fat_g FROM profiles"
        )
    ).all()
    targets = sa.table(
        "nutrition_targets",
        sa.column("id", sa.String),
        sa.column("owner_id", sa.String),
        sa.column("version", sa.Integer),
        sa.column("effective_date", sa.Date),
        sa.column("calories", sa.Integer),
        sa.column("protein_g", sa.Numeric),
        sa.column("carbs_g", sa.Numeric),
        sa.column("fat_g", sa.Numeric),
        sa.column("source", sa.Enum("INITIAL", "MANUAL", "CHECK_IN", name="nutrition_target_source")),
        sa.column("created_utc", sa.DateTime(timezone=True)),
    )
    rows = []
    for user_id, timezone, created, calories, protein, carbs, fat in profiles:
        if isinstance(created, str):  # SQLite returns timestamps as text
            created = datetime.fromisoformat(created)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        try:
            zone = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            zone = ZoneInfo("UTC")
        rows.append(
            {
                "id": user_id,
                "owner_id": user_id,
                "version": 1,
                "effective_date": created.astimezone(zone).date(),
                "calories": calories,
                "protein_g": protein,
                "carbs_g": carbs,
                "fat_g": fat,
                "source": "INITIAL",
                "created_utc": created,
            }
        )
    if rows:
        op.bulk_insert(targets, rows)
    with op.batch_alter_table("profiles") as batch:
        for column in _TARGET_COLUMNS:
            batch.drop_column(column)


def downgrade() -> None:
    # Put the newest version of each user's targets back on their profile; the history is lost.
    with op.batch_alter_table("profiles") as batch:
        batch.add_column(sa.Column("target_calories", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("target_protein_g", sa.Numeric(precision=6, scale=1), nullable=True))
        batch.add_column(sa.Column("target_carbs_g", sa.Numeric(precision=6, scale=1), nullable=True))
        batch.add_column(sa.Column("target_fat_g", sa.Numeric(precision=6, scale=1), nullable=True))
    latest = "FROM nutrition_targets t WHERE t.owner_id = profiles.user_id ORDER BY t.version DESC LIMIT 1"
    op.execute(
        "UPDATE profiles SET "
        f"target_calories = COALESCE((SELECT t.calories {latest}), 2200), "
        f"target_protein_g = COALESCE((SELECT t.protein_g {latest}), 150), "
        f"target_carbs_g = COALESCE((SELECT t.carbs_g {latest}), 230), "
        f"target_fat_g = COALESCE((SELECT t.fat_g {latest}), 70)"
    )
    with op.batch_alter_table("profiles") as batch:
        for column in _TARGET_COLUMNS:
            batch.alter_column(column, nullable=False)
    op.drop_index("uq_nutrition_targets_owner_version", table_name="nutrition_targets")
    op.drop_table("nutrition_targets")
    sa.Enum(name="nutrition_target_source").drop(op.get_bind(), checkfirst=True)
