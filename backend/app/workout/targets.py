"""A routine exercise's working-set targets, read and adjusted as a whole.

A routine stores each set's own targets (``planned_sets``). Check-ins speak about
an exercise as a whole: how many working sets, and its target weight and reps.
These functions are the single translation between the two, used both to describe
a routine to the workout agent and to apply an accepted change to it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC
from typing import Any, Literal

from .models import SetKind, WorkoutPlanEntry

TargetField = Literal["working_sets", "target_weight_kg", "target_reps"]
TARGET_FIELDS: tuple[TargetField, ...] = ("working_sets", "target_weight_kg", "target_reps")


def _is_working(planned_set: dict[str, Any]) -> bool:
    # Working sets only: warm-ups don't count, and failure/drop sets are extras on top.
    return planned_set.get("kind") == SetKind.WORKING.value


def working_targets(planned_sets: Sequence[dict[str, Any]]) -> dict[str, float | None]:
    """How many working sets there are, and the heaviest target weight and highest target
    reps among them (sets and reps as whole numbers)."""

    working = [planned_set for planned_set in planned_sets if _is_working(planned_set)]
    weights = [float(s["target_weight_kg"]) for s in working if s.get("target_weight_kg") is not None]
    reps = [int(s["target_reps"]) for s in working if s.get("target_reps") is not None]
    return {
        "working_sets": len(working),
        "target_weight_kg": max(weights) if weights else None,
        "target_reps": max(reps) if reps else None,
    }


def adjust_targets(
    planned_sets: Sequence[dict[str, Any]], field: TargetField, value: float, *, load_step: float = 2.5
) -> list[dict[str, Any]]:
    """``planned_sets`` with one target changed; warm-ups and extra sets are left as they are.

    More working sets copy the last working set, fewer drop the last ones. A new target
    weight or reps keeps the sets' shape: the heaviest set gets the new weight and the
    others the same proportion of theirs (rounded to ``load_step`` towards their own
    weight), and every set's reps move by the same number. So a pyramid stays a pyramid,
    and no set changes by more than the exercise as a whole.
    """

    sets = [dict(planned_set) for planned_set in planned_sets]
    working = [index for index, planned_set in enumerate(sets) if _is_working(planned_set)]
    if field == "working_sets":
        wanted = int(value)
        if wanted < len(working):
            dropped = set(working[wanted:])
            return [planned_set for index, planned_set in enumerate(sets) if index not in dropped]
        template = (
            dict(sets[working[-1]])
            if working
            else {"kind": SetKind.WORKING.value, "target_weight_kg": None, "target_reps": None}
        )
        insert_at = working[-1] + 1 if working else len(sets)
        return sets[:insert_at] + [dict(template) for _ in range(wanted - len(working))] + sets[insert_at:]

    current = working_targets(sets)[field]
    if current is None:
        return sets
    for index in working:
        own = sets[index].get(field)
        if own is None:
            continue
        if field == "target_reps":
            sets[index][field] = max(1, int(own) + int(value) - int(current))
        elif float(own) == current or current == 0:
            sets[index][field] = value
        else:
            # Rounded towards the set's own weight, so it never moves by more than the whole.
            scaled = float(own) * value / current / load_step
            steps = math.ceil(scaled - 1e-9) if value < current else math.floor(scaled + 1e-9)
            sets[index][field] = max(0.0, steps * load_step)
    return sets


def routine_revision(routine: WorkoutPlanEntry) -> str:
    """When the routine was last saved: a check-in records it, and a change made from
    that check-in is refused if the routine was saved again since."""

    moment = routine.updated_utc or routine.created_utc
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).isoformat()
