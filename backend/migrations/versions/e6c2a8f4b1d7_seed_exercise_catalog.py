"""seed the built-in exercise catalogue

Revision ID: e6c2a8f4b1d7
Revises: d5a1c7e3f9b4
Create Date: 2026-10-22 15:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, insert

# revision identifiers, used by Alembic.
revision: str = "e6c2a8f4b1d7"
down_revision: str | None = "d5a1c7e3f9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Migration data is intentionally frozen here. Future catalogue additions need
# a new additive migration so databases that already ran this revision receive them.
EQUIPMENT = ("barbell", "dumbbell", "cable", "machine", "bodyweight", "kettlebell", "band")
EXERCISES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("exercise-bench-press", "Barbell Bench Press", "barbell", ("chest", "triceps", "shoulders")),
    ("exercise-incline-bench", "Incline Barbell Bench Press", "barbell", ("chest", "shoulders", "triceps")),
    ("exercise-db-bench", "Dumbbell Bench Press", "dumbbell", ("chest", "triceps", "shoulders")),
    (
        "exercise-db-incline-bench",
        "Incline Dumbbell Bench Press",
        "dumbbell",
        ("chest", "shoulders", "triceps"),
    ),
    ("exercise-chest-press", "Machine Chest Press", "machine", ("chest", "triceps", "shoulders")),
    ("exercise-cable-fly", "Cable Chest Fly", "cable", ("chest",)),
    ("exercise-db-fly", "Dumbbell Chest Fly", "dumbbell", ("chest",)),
    ("exercise-push-up", "Push-Up", "bodyweight", ("chest", "triceps", "shoulders", "core")),
    ("exercise-chest-dip", "Chest Dip", "bodyweight", ("chest", "triceps", "shoulders")),
    ("exercise-deadlift", "Barbell Deadlift", "barbell", ("back", "hamstrings", "glutes")),
    ("exercise-lat-pulldown", "Lat Pulldown", "cable", ("back", "biceps")),
    ("exercise-pull-up", "Pull-Up", "bodyweight", ("back", "biceps", "core")),
    ("exercise-assisted-pull-up", "Assisted Pull-Up", "machine", ("back", "biceps")),
    ("exercise-seated-cable-row", "Seated Cable Row", "cable", ("back", "biceps")),
    ("exercise-bb-row", "Barbell Bent-Over Row", "barbell", ("back", "biceps", "shoulders")),
    ("exercise-one-arm-db-row", "One-Arm Dumbbell Row", "dumbbell", ("back", "biceps")),
    (
        "exercise-chest-supported-row",
        "Chest-Supported Dumbbell Row",
        "dumbbell",
        ("back", "biceps", "shoulders"),
    ),
    ("exercise-machine-row", "Machine Row", "machine", ("back", "biceps")),
    ("exercise-straight-arm-pulldown", "Straight-Arm Pulldown", "cable", ("back",)),
    ("exercise-back-extension", "Back Extension", "bodyweight", ("back", "hamstrings", "glutes")),
    ("exercise-band-row", "Resistance Band Row", "band", ("back", "biceps")),
    ("exercise-overhead-press", "Barbell Overhead Press", "barbell", ("shoulders", "triceps", "core")),
    ("exercise-db-shoulder-press", "Dumbbell Shoulder Press", "dumbbell", ("shoulders", "triceps")),
    ("exercise-machine-shoulder-press", "Machine Shoulder Press", "machine", ("shoulders", "triceps")),
    ("exercise-db-lateral-raise", "Dumbbell Lateral Raise", "dumbbell", ("shoulders",)),
    ("exercise-cable-lateral-raise", "Cable Lateral Raise", "cable", ("shoulders",)),
    ("exercise-reverse-fly", "Reverse Dumbbell Fly", "dumbbell", ("shoulders", "back")),
    ("exercise-face-pull", "Cable Face Pull", "cable", ("shoulders", "back")),
    ("exercise-db-front-raise", "Dumbbell Front Raise", "dumbbell", ("shoulders",)),
    ("exercise-band-pull-apart", "Resistance Band Pull-Apart", "band", ("shoulders", "back")),
    ("exercise-bb-curl", "Barbell Curl", "barbell", ("biceps",)),
    ("exercise-ez-curl", "EZ-Bar Curl", "barbell", ("biceps",)),
    ("exercise-db-curl", "Dumbbell Curl", "dumbbell", ("biceps",)),
    ("exercise-hammer-curl", "Hammer Curl", "dumbbell", ("biceps",)),
    ("exercise-incline-db-curl", "Incline Dumbbell Curl", "dumbbell", ("biceps",)),
    ("exercise-cable-curl", "Cable Curl", "cable", ("biceps",)),
    ("exercise-preacher-curl", "Preacher Curl", "machine", ("biceps",)),
    ("exercise-triceps-pushdown", "Cable Triceps Pushdown", "cable", ("triceps",)),
    ("exercise-overhead-triceps", "Overhead Cable Triceps Extension", "cable", ("triceps",)),
    ("exercise-skull-crusher", "Barbell Skull Crusher", "barbell", ("triceps",)),
    ("exercise-close-grip-bench", "Close-Grip Bench Press", "barbell", ("triceps", "chest", "shoulders")),
    ("exercise-db-triceps-extension", "Dumbbell Overhead Triceps Extension", "dumbbell", ("triceps",)),
    ("exercise-bench-dip", "Bench Dip", "bodyweight", ("triceps", "chest", "shoulders")),
    ("exercise-squat", "Barbell Back Squat", "barbell", ("quads", "glutes")),
    ("exercise-front-squat", "Barbell Front Squat", "barbell", ("quads", "glutes", "core")),
    ("exercise-goblet-squat", "Kettlebell Goblet Squat", "kettlebell", ("quads", "glutes", "core")),
    ("exercise-leg-press", "Leg Press", "machine", ("quads", "glutes")),
    ("exercise-hack-squat", "Hack Squat", "machine", ("quads", "glutes")),
    ("exercise-split-squat", "Dumbbell Split Squat", "dumbbell", ("quads", "glutes")),
    ("exercise-bulgarian-split-squat", "Bulgarian Split Squat", "dumbbell", ("quads", "glutes")),
    ("exercise-walking-lunge", "Dumbbell Walking Lunge", "dumbbell", ("quads", "glutes", "hamstrings")),
    ("exercise-leg-extension", "Leg Extension", "machine", ("quads",)),
    ("exercise-step-up", "Dumbbell Step-Up", "dumbbell", ("quads", "glutes")),
    ("exercise-rdl", "Barbell Romanian Deadlift", "barbell", ("hamstrings", "glutes", "back")),
    ("exercise-db-rdl", "Dumbbell Romanian Deadlift", "dumbbell", ("hamstrings", "glutes", "back")),
    ("exercise-stiff-leg-deadlift", "Stiff-Leg Deadlift", "barbell", ("hamstrings", "glutes", "back")),
    ("exercise-lying-leg-curl", "Lying Leg Curl", "machine", ("hamstrings",)),
    ("exercise-seated-leg-curl", "Seated Leg Curl", "machine", ("hamstrings",)),
    ("exercise-hip-thrust", "Barbell Hip Thrust", "barbell", ("glutes", "hamstrings")),
    ("exercise-glute-bridge", "Glute Bridge", "bodyweight", ("glutes", "hamstrings", "core")),
    ("exercise-cable-pull-through", "Cable Pull-Through", "cable", ("glutes", "hamstrings")),
    ("exercise-kb-swing", "Kettlebell Swing", "kettlebell", ("glutes", "hamstrings", "core")),
    ("exercise-band-lateral-walk", "Resistance Band Lateral Walk", "band", ("glutes",)),
    ("exercise-standing-calf-raise", "Standing Calf Raise", "machine", ("calves",)),
    ("exercise-seated-calf-raise", "Seated Calf Raise", "machine", ("calves",)),
    ("exercise-leg-press-calf", "Leg Press Calf Raise", "machine", ("calves",)),
    ("exercise-single-leg-calf", "Single-Leg Calf Raise", "bodyweight", ("calves",)),
    ("exercise-plank", "Plank", "bodyweight", ("core",)),
    ("exercise-side-plank", "Side Plank", "bodyweight", ("core",)),
    ("exercise-hanging-knee-raise", "Hanging Knee Raise", "bodyweight", ("core",)),
    ("exercise-cable-crunch", "Cable Crunch", "cable", ("core",)),
    ("exercise-ab-wheel", "Ab Wheel Rollout", "bodyweight", ("core",)),
    ("exercise-russian-twist", "Russian Twist", "bodyweight", ("core",)),
    ("exercise-dead-bug", "Dead Bug", "bodyweight", ("core",)),
    ("exercise-pallof-press", "Cable Pallof Press", "cable", ("core",)),
    ("exercise-farmer-carry", "Dumbbell Farmer Carry", "dumbbell", ("core", "shoulders")),
)


exercises = sa.table(
    "exercises",
    sa.column("id", sa.String),
    sa.column("owner_id", sa.String),
    sa.column("name", sa.String),
    sa.column("equipment", ENUM(*EQUIPMENT, name="equipment", create_type=False)),
    sa.column("muscles", sa.JSON),
    sa.column("created_utc", sa.DateTime(timezone=True)),
    sa.column("updated_utc", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    # Three of these ids existed in the old demo seed. Keep those rows and add every
    # missing global exercise, so the migration is safe on an existing local database.
    now = datetime.now(UTC)
    rows = [
        {
            "id": exercise_id,
            "owner_id": None,
            "name": name,
            "equipment": equipment,
            "muscles": list(muscles),
            "created_utc": now,
        }
        for exercise_id, name, equipment, muscles in EXERCISES
    ]
    op.get_bind().execute(insert(exercises).values(rows).on_conflict_do_nothing(index_elements=["id"]))


def downgrade() -> None:
    # Data migrations are intentionally non-destructive on downgrade. Some rows may
    # have existed before this migration, and routines or history may now refer to them.
    pass
