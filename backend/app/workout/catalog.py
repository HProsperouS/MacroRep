"""The built-in exercise catalogue.

This is deliberately small, original metadata rather than a copy of another app's
catalogue: enough common movements that creating a custom exercise is the exception.
Ids are permanent because routines and workout history refer to them. Add new rows
with a new additive Alembic migration; never reuse an old id for another movement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EQUIPMENT, MUSCLE_GROUPS, Exercise


@dataclass(frozen=True)
class CatalogExercise:
    id: str
    name: str
    equipment: str
    muscles: tuple[str, ...]

    def row(self) -> dict[str, object]:
        return {
            "id": self.id,
            "owner_id": None,
            "name": self.name,
            "equipment": self.equipment,
            "muscles": list(self.muscles),
        }


def _exercise(id: str, name: str, equipment: str, *muscles: str) -> CatalogExercise:
    return CatalogExercise(id=id, name=name, equipment=equipment, muscles=muscles)


SYSTEM_EXERCISES: tuple[CatalogExercise, ...] = (
    # Chest
    _exercise("exercise-bench-press", "Barbell Bench Press", "barbell", "chest", "triceps", "shoulders"),
    _exercise(
        "exercise-incline-bench",
        "Incline Barbell Bench Press",
        "barbell",
        "chest",
        "shoulders",
        "triceps",
    ),
    _exercise("exercise-db-bench", "Dumbbell Bench Press", "dumbbell", "chest", "triceps", "shoulders"),
    _exercise(
        "exercise-db-incline-bench",
        "Incline Dumbbell Bench Press",
        "dumbbell",
        "chest",
        "shoulders",
        "triceps",
    ),
    _exercise("exercise-chest-press", "Machine Chest Press", "machine", "chest", "triceps", "shoulders"),
    _exercise("exercise-cable-fly", "Cable Chest Fly", "cable", "chest"),
    _exercise("exercise-db-fly", "Dumbbell Chest Fly", "dumbbell", "chest"),
    _exercise("exercise-push-up", "Push-Up", "bodyweight", "chest", "triceps", "shoulders", "core"),
    _exercise("exercise-chest-dip", "Chest Dip", "bodyweight", "chest", "triceps", "shoulders"),
    # Back
    _exercise("exercise-deadlift", "Barbell Deadlift", "barbell", "back", "hamstrings", "glutes"),
    _exercise("exercise-lat-pulldown", "Lat Pulldown", "cable", "back", "biceps"),
    _exercise("exercise-pull-up", "Pull-Up", "bodyweight", "back", "biceps", "core"),
    _exercise("exercise-assisted-pull-up", "Assisted Pull-Up", "machine", "back", "biceps"),
    _exercise("exercise-seated-cable-row", "Seated Cable Row", "cable", "back", "biceps"),
    _exercise("exercise-bb-row", "Barbell Bent-Over Row", "barbell", "back", "biceps", "shoulders"),
    _exercise("exercise-one-arm-db-row", "One-Arm Dumbbell Row", "dumbbell", "back", "biceps"),
    _exercise(
        "exercise-chest-supported-row",
        "Chest-Supported Dumbbell Row",
        "dumbbell",
        "back",
        "biceps",
        "shoulders",
    ),
    _exercise("exercise-machine-row", "Machine Row", "machine", "back", "biceps"),
    _exercise("exercise-straight-arm-pulldown", "Straight-Arm Pulldown", "cable", "back"),
    _exercise("exercise-back-extension", "Back Extension", "bodyweight", "back", "hamstrings", "glutes"),
    _exercise("exercise-band-row", "Resistance Band Row", "band", "back", "biceps"),
    # Shoulders
    _exercise("exercise-overhead-press", "Barbell Overhead Press", "barbell", "shoulders", "triceps", "core"),
    _exercise("exercise-db-shoulder-press", "Dumbbell Shoulder Press", "dumbbell", "shoulders", "triceps"),
    _exercise("exercise-machine-shoulder-press", "Machine Shoulder Press", "machine", "shoulders", "triceps"),
    _exercise("exercise-db-lateral-raise", "Dumbbell Lateral Raise", "dumbbell", "shoulders"),
    _exercise("exercise-cable-lateral-raise", "Cable Lateral Raise", "cable", "shoulders"),
    _exercise("exercise-reverse-fly", "Reverse Dumbbell Fly", "dumbbell", "shoulders", "back"),
    _exercise("exercise-face-pull", "Cable Face Pull", "cable", "shoulders", "back"),
    _exercise("exercise-db-front-raise", "Dumbbell Front Raise", "dumbbell", "shoulders"),
    _exercise("exercise-band-pull-apart", "Resistance Band Pull-Apart", "band", "shoulders", "back"),
    # Arms
    _exercise("exercise-bb-curl", "Barbell Curl", "barbell", "biceps"),
    _exercise("exercise-ez-curl", "EZ-Bar Curl", "barbell", "biceps"),
    _exercise("exercise-db-curl", "Dumbbell Curl", "dumbbell", "biceps"),
    _exercise("exercise-hammer-curl", "Hammer Curl", "dumbbell", "biceps"),
    _exercise("exercise-incline-db-curl", "Incline Dumbbell Curl", "dumbbell", "biceps"),
    _exercise("exercise-cable-curl", "Cable Curl", "cable", "biceps"),
    _exercise("exercise-preacher-curl", "Preacher Curl", "machine", "biceps"),
    _exercise("exercise-triceps-pushdown", "Cable Triceps Pushdown", "cable", "triceps"),
    _exercise("exercise-overhead-triceps", "Overhead Cable Triceps Extension", "cable", "triceps"),
    _exercise("exercise-skull-crusher", "Barbell Skull Crusher", "barbell", "triceps"),
    _exercise(
        "exercise-close-grip-bench",
        "Close-Grip Bench Press",
        "barbell",
        "triceps",
        "chest",
        "shoulders",
    ),
    _exercise("exercise-db-triceps-extension", "Dumbbell Overhead Triceps Extension", "dumbbell", "triceps"),
    _exercise("exercise-bench-dip", "Bench Dip", "bodyweight", "triceps", "chest", "shoulders"),
    # Quads and compound legs
    _exercise("exercise-squat", "Barbell Back Squat", "barbell", "quads", "glutes"),
    _exercise("exercise-front-squat", "Barbell Front Squat", "barbell", "quads", "glutes", "core"),
    _exercise("exercise-goblet-squat", "Kettlebell Goblet Squat", "kettlebell", "quads", "glutes", "core"),
    _exercise("exercise-leg-press", "Leg Press", "machine", "quads", "glutes"),
    _exercise("exercise-hack-squat", "Hack Squat", "machine", "quads", "glutes"),
    _exercise("exercise-split-squat", "Dumbbell Split Squat", "dumbbell", "quads", "glutes"),
    _exercise("exercise-bulgarian-split-squat", "Bulgarian Split Squat", "dumbbell", "quads", "glutes"),
    _exercise(
        "exercise-walking-lunge",
        "Dumbbell Walking Lunge",
        "dumbbell",
        "quads",
        "glutes",
        "hamstrings",
    ),
    _exercise("exercise-leg-extension", "Leg Extension", "machine", "quads"),
    _exercise("exercise-step-up", "Dumbbell Step-Up", "dumbbell", "quads", "glutes"),
    # Hamstrings and glutes
    _exercise("exercise-rdl", "Barbell Romanian Deadlift", "barbell", "hamstrings", "glutes", "back"),
    _exercise("exercise-db-rdl", "Dumbbell Romanian Deadlift", "dumbbell", "hamstrings", "glutes", "back"),
    _exercise("exercise-stiff-leg-deadlift", "Stiff-Leg Deadlift", "barbell", "hamstrings", "glutes", "back"),
    _exercise("exercise-lying-leg-curl", "Lying Leg Curl", "machine", "hamstrings"),
    _exercise("exercise-seated-leg-curl", "Seated Leg Curl", "machine", "hamstrings"),
    _exercise("exercise-hip-thrust", "Barbell Hip Thrust", "barbell", "glutes", "hamstrings"),
    _exercise("exercise-glute-bridge", "Glute Bridge", "bodyweight", "glutes", "hamstrings", "core"),
    _exercise("exercise-cable-pull-through", "Cable Pull-Through", "cable", "glutes", "hamstrings"),
    _exercise("exercise-kb-swing", "Kettlebell Swing", "kettlebell", "glutes", "hamstrings", "core"),
    _exercise("exercise-band-lateral-walk", "Resistance Band Lateral Walk", "band", "glutes"),
    # Calves
    _exercise("exercise-standing-calf-raise", "Standing Calf Raise", "machine", "calves"),
    _exercise("exercise-seated-calf-raise", "Seated Calf Raise", "machine", "calves"),
    _exercise("exercise-leg-press-calf", "Leg Press Calf Raise", "machine", "calves"),
    _exercise("exercise-single-leg-calf", "Single-Leg Calf Raise", "bodyweight", "calves"),
    # Core
    _exercise("exercise-plank", "Plank", "bodyweight", "core"),
    _exercise("exercise-side-plank", "Side Plank", "bodyweight", "core"),
    _exercise("exercise-hanging-knee-raise", "Hanging Knee Raise", "bodyweight", "core"),
    _exercise("exercise-cable-crunch", "Cable Crunch", "cable", "core"),
    _exercise("exercise-ab-wheel", "Ab Wheel Rollout", "bodyweight", "core"),
    _exercise("exercise-russian-twist", "Russian Twist", "bodyweight", "core"),
    _exercise("exercise-dead-bug", "Dead Bug", "bodyweight", "core"),
    _exercise("exercise-pallof-press", "Cable Pallof Press", "cable", "core"),
    _exercise("exercise-farmer-carry", "Dumbbell Farmer Carry", "dumbbell", "core", "shoulders"),
)


def validate_catalogue() -> None:
    """Fail fast when a catalogue edit would make stored or searchable data ambiguous."""

    ids: set[str] = set()
    names: set[str] = set()
    for exercise in SYSTEM_EXERCISES:
        if not re.fullmatch(r"[a-z0-9-]+", exercise.id) or len(exercise.id) > 40:
            raise ValueError(f"Invalid exercise catalogue id: {exercise.id!r}")
        if exercise.id in ids:
            raise ValueError(f"Duplicate exercise catalogue id: {exercise.id}")
        ids.add(exercise.id)

        normalized_name = exercise.name.casefold()
        if not exercise.name.strip() or normalized_name in names:
            raise ValueError(f"Duplicate or empty exercise catalogue name: {exercise.name!r}")
        names.add(normalized_name)

        if exercise.equipment not in EQUIPMENT:
            raise ValueError(f"Unknown equipment for {exercise.id}: {exercise.equipment}")
        if not 1 <= len(exercise.muscles) <= 4 or len(set(exercise.muscles)) != len(exercise.muscles):
            raise ValueError(f"Invalid muscle list for {exercise.id}")
        unknown = set(exercise.muscles) - set(MUSCLE_GROUPS)
        if unknown:
            raise ValueError(f"Unknown muscles for {exercise.id}: {sorted(unknown)}")


validate_catalogue()


async def ensure_system_exercises(session: AsyncSession) -> int:
    """Install missing built-in exercises without changing existing rows.

    The caller owns the transaction. Returning the number added keeps startup
    and migration-path tests observable without coupling them to demo data.
    """

    catalogue_ids = [exercise.id for exercise in SYSTEM_EXERCISES]
    existing_ids = set(await session.scalars(select(Exercise.id).where(Exercise.id.in_(catalogue_ids))))
    missing = [Exercise(**exercise.row()) for exercise in SYSTEM_EXERCISES if exercise.id not in existing_ids]
    if missing:
        session.add_all(missing)
        await session.flush()
    return len(missing)
