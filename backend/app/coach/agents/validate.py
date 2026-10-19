"""Deterministic checks between the agents' advice and the user.

Agents interpret; these functions decide what may actually be proposed. They hold
every value to ``limits``, drop anything that refers to a routine or exercise the
user doesn't have, and settle a nutrition/training conflict whatever the reviewer
said. Each returns notes explaining what it changed, shown to the user.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from . import limits
from .schemas import NutritionAdvice, WorkoutAdvice


def _round_to(value: float, step: float) -> float:
    return round(value / step) * step


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round_within(value: float, low: float, high: float, step: float) -> float | None:
    """``value`` rounded to ``step`` and kept inside [low, high], rounding inwards at the
    edges so the rounding itself can never cross a limit. None when no step fits inside."""

    lowest = math.ceil(low / step - 1e-9) * step
    highest = math.floor(high / step + 1e-9) * step
    if lowest > highest:
        return None
    return _clamp(_round_to(value, step), lowest, highest)


def validate_nutrition(advice: NutritionAdvice | None, current: int) -> tuple[int | None, list[str]]:
    """The calorie target to propose, or None for no change, and notes on any limit applied."""

    if advice is None or advice.action != "change" or advice.new_calorie_target is None:
        return None, []
    notes: list[str] = []
    proposed = advice.new_calorie_target
    low = max(current - limits.MAX_WEEKLY_CALORIE_CHANGE, limits.MIN_TARGET_CALORIES)
    high = min(current + limits.MAX_WEEKLY_CALORIE_CHANGE, limits.MAX_TARGET_CALORIES)
    rounded = _round_within(proposed, low, high, limits.CALORIE_STEP)
    if rounded is None:
        return None, notes
    target = int(rounded)
    if abs(proposed - target) >= limits.CALORIE_STEP:
        notes.append(
            f"The calorie change was limited to {target:,} kcal (proposed {proposed:,}): one check-in "
            f"changes the target by at most {limits.MAX_WEEKLY_CALORIE_CHANGE} kcal, within "
            f"{limits.MIN_TARGET_CALORIES:,}-{limits.MAX_TARGET_CALORIES:,} kcal."
        )
    if target == current:
        return None, notes
    return target, notes


@dataclass(frozen=True)
class ValidAdjustment:
    routine_id: str
    routine_name: str
    exercise_id: str
    exercise_name: str
    field: str
    before: float
    after: float
    reason: str

    @property
    def increases_load(self) -> bool:
        return self.after > self.before


def find_exercise(
    routines: Sequence[Mapping[str, Any]], routine_id: str, exercise_id: str
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    """The scheduled routine and exercise a training change refers to, if the user has them."""

    for routine in routines:
        if routine["routine_id"] != routine_id:
            continue
        for exercise in routine["exercises"]:
            if exercise["exercise_id"] == exercise_id:
                return routine, exercise
    return None


def _bounded(field: str, before: float, wanted: float) -> float:
    if field == "working_sets":
        value = _clamp(round(wanted), before - limits.MAX_SET_CHANGE, before + limits.MAX_SET_CHANGE)
        return _clamp(value, limits.MIN_WORKING_SETS, limits.MAX_WORKING_SETS)
    if field == "target_reps":
        value = _clamp(round(wanted), before - limits.MAX_REP_CHANGE, before + limits.MAX_REP_CHANGE)
        return _clamp(value, limits.MIN_TARGET_REPS, limits.MAX_TARGET_REPS)
    room = before * limits.MAX_LOAD_CHANGE_SHARE
    # A light weight may have no plate step within the limit at all: then it stays as it is.
    bounded = _round_within(wanted, max(0.0, before - room), before + room, limits.LOAD_STEP_KG)
    return before if bounded is None else bounded


def validate_workout(
    advice: WorkoutAdvice | None, routines: Sequence[Mapping[str, Any]]
) -> tuple[list[ValidAdjustment], list[str]]:
    """The adjustments to propose, each within limits, and notes on what was dropped or limited."""

    if advice is None or advice.action != "change":
        return [], []
    kept: list[ValidAdjustment] = []
    notes: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for adjustment in advice.adjustments:
        key = (adjustment.routine_id, adjustment.exercise_id, adjustment.field)
        found = find_exercise(routines, adjustment.routine_id, adjustment.exercise_id)
        if found is None:
            notes.append(
                "A training change for an exercise that isn't in your scheduled routines was dropped."
            )
            continue
        if key in seen:
            continue
        seen.add(key)
        routine, exercise = found
        current = exercise[adjustment.field]
        if current is None:
            notes.append(
                f"{exercise['name']} has no {adjustment.field.replace('_', ' ')} set, so it wasn't changed."
            )
            continue
        before = float(current)
        after = _bounded(adjustment.field, before, adjustment.new_value)
        if after == before:
            continue
        step = limits.LOAD_STEP_KG if adjustment.field == "target_weight_kg" else 1
        if after != _round_to(adjustment.new_value, step):
            notes.append(f"The change to {exercise['name']} was limited to a safe step.")
        kept.append(
            ValidAdjustment(
                routine_id=routine["routine_id"],
                routine_name=routine["name"],
                exercise_id=exercise["exercise_id"],
                exercise_name=exercise["name"],
                field=adjustment.field,
                before=before,
                after=after,
                reason=adjustment.reason,
            )
        )
        if len(kept) == limits.MAX_WORKOUT_ADJUSTMENTS:
            break
    return kept, notes


def resolve_conflicts(
    new_calorie_target: int | None, current_calorie_target: int, adjustments: list[ValidAdjustment]
) -> tuple[list[ValidAdjustment], list[str]]:
    """Eating less while training harder undercuts recovery (plan.md §2): when the
    calorie target goes down, training load can't go up in the same check-in."""

    cutting = new_calorie_target is not None and new_calorie_target < current_calorie_target
    if not cutting or not any(adjustment.increases_load for adjustment in adjustments):
        return adjustments, []
    return [adjustment for adjustment in adjustments if not adjustment.increases_load], [
        "Training increases were held back because the calorie target is going down this week."
    ]
