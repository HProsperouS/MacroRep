"""set load and session bodyweight

Bodyweight sets count the lifter's bodyweight plus anything added, and band sets are
tracked by reps (their kg is a guess). Each set gets the load its analytics use
(``load_kg``) and each workout the bodyweight it was logged at (``body_weight_kg``).

Existing workouts take the latest weigh-in on or before the day they were started (as a
UTC date: close enough for a weigh-in that is at most a day out).

Revision ID: d3a7c5e1f9b2
Revises: b2f6d8a4c1e9
Create Date: 2026-11-13 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3a7c5e1f9b2"
down_revision: str | None = "b2f6d8a4c1e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workout_sessions", sa.Column("body_weight_kg", sa.Numeric(5, 2), nullable=True))
    op.add_column("workout_set_logs", sa.Column("load_kg", sa.Numeric(7, 2), nullable=True))
    op.execute(
        """
        UPDATE workout_sessions AS s
        SET body_weight_kg = (
            SELECT w.weight_kg FROM weigh_ins AS w
            WHERE w.owner_id = s.owner_id AND w.log_date <= (s.started_at AT TIME ZONE 'UTC')::date
            ORDER BY w.log_date DESC
            LIMIT 1
        )
        """
    )
    # The same rules as app.analytics.training.effective_load_kg.
    op.execute(
        """
        UPDATE workout_set_logs AS l
        SET load_kg = CASE
            WHEN e.equipment = 'band' THEN 0
            WHEN e.equipment = 'bodyweight' AND s.body_weight_kg IS NOT NULL
                THEN l.weight_kg + s.body_weight_kg
            ELSE l.weight_kg
        END
        FROM workout_sessions AS s, exercises AS e
        WHERE s.id = l.session_id AND e.id = l.exercise_id
        """
    )
    # Sets whose exercise was removed from the catalog keep what was typed.
    op.execute("UPDATE workout_set_logs SET load_kg = weight_kg WHERE load_kg IS NULL")
    op.alter_column("workout_set_logs", "load_kg", nullable=False)


def downgrade() -> None:
    op.drop_column("workout_set_logs", "load_kg")
    op.drop_column("workout_sessions", "body_weight_kg")
