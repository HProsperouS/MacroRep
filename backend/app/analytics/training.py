"""Strength and training-load calculations.

Callers decide which sets to pass in. By convention only *working* sets are
counted for volume, estimated 1RM, and personal records; warmups are excluded
so a heavy warmup can neither inflate volume nor mask a genuine PR.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta


def estimated_one_rep_max(weight_kg: float, reps: int) -> float | None:
    """Epley estimate of the most weight that could be lifted for one rep.

    ``weight * (1 + reps / 30)``. A single rep *is* a one-rep max, so it
    returns the weight itself rather than Epley's 3% uplift. A set with no
    completed reps says nothing about strength and returns None.
    """

    if reps < 1 or weight_kg <= 0:
        return None
    if reps == 1:
        return float(weight_kg)
    return float(weight_kg) * (1 + reps / 30)


def best_estimated_one_rep_max(sets: Iterable[tuple[float, int]]) -> float | None:
    """The highest estimated 1RM across (weight_kg, reps) sets, or None if none qualify."""

    estimates = [
        estimate
        for weight_kg, reps in sets
        if (estimate := estimated_one_rep_max(weight_kg, reps)) is not None
    ]
    return max(estimates) if estimates else None


def is_personal_record(best_new: float | None, best_before: float | None) -> bool:
    """A new best counts as a PR when it beats every earlier best, or there was none."""

    if best_new is None:
        return False
    return best_before is None or best_new > best_before


def volume_kg(sets: Iterable[tuple[float, int]]) -> float:
    """Training volume (tonnage): the sum of weight x reps over (weight_kg, reps) sets."""

    return sum(float(weight_kg) * reps for weight_kg, reps in sets)


def week_start(day: date) -> date:
    """The Monday of the ISO week containing ``day``."""

    return day - timedelta(days=day.weekday())


def weekly_volume_kg(sets: Iterable[tuple[date, float, int]]) -> dict[date, float]:
    """Volume per week from (session date, weight_kg, reps) sets, keyed by week start."""

    totals: dict[date, float] = {}
    for day, weight_kg, reps in sets:
        week = week_start(day)
        totals[week] = totals.get(week, 0.0) + float(weight_kg) * reps
    return totals


def average_rpe_by_week(entries: Iterable[tuple[date, float]]) -> dict[date, float]:
    """Mean RPE per week from (session date, rpe) pairs, keyed by week start.

    Sets without an RPE should not be passed in: logging RPE is optional, and a
    missing value is not a low effort.
    """

    sums: dict[date, float] = {}
    counts: dict[date, int] = {}
    for day, rpe in entries:
        week = week_start(day)
        sums[week] = sums.get(week, 0.0) + float(rpe)
        counts[week] = counts.get(week, 0) + 1
    return {week: round(sums[week] / counts[week], 1) for week in sums}


def completion_percent(done: int, planned: int) -> float | None:
    """Workouts done as a percentage of those planned, or None when nothing was planned.

    Not capped at 100: training more often than planned is reported as such.
    """

    if planned <= 0:
        return None
    return round(done / planned * 100, 1)


def percent_change(before: float, after: float) -> float | None:
    """Relative change from ``before`` to ``after`` as a percentage, or None if ``before`` is 0."""

    if before == 0:
        return None
    return round((after - before) / before * 100, 1)
