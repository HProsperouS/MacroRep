from __future__ import annotations

from datetime import date

import pytest

from app.analytics.training import (
    average_rpe,
    average_rpe_by_week,
    best_estimated_one_rep_max,
    completion_percent,
    estimated_one_rep_max,
    is_personal_record,
    percent_change,
    planned_sessions,
    volume_kg,
    week_start,
    weekly_volume_kg,
)

# 2024-01-01 is a Monday.
WEEK_1, WEEK_2 = date(2024, 1, 1), date(2024, 1, 8)


@pytest.mark.parametrize(
    ("weight_kg", "reps", "expected"),
    [
        (100, 5, 116.67),  # Epley: 100 * (1 + 5/30)
        (60, 10, 80.0),  # 60 * (1 + 10/30)
        (100, 1, 100.0),  # a single rep is itself the 1RM
        (100, 0, None),  # a failed set says nothing about strength
        (0, 5, None),  # bodyweight-only / unloaded sets aren't estimated
    ],
)
def test_estimated_one_rep_max(weight_kg: float, reps: int, expected: float | None) -> None:
    result = estimated_one_rep_max(weight_kg, reps)
    assert (round(result, 2) if result is not None else None) == expected


def test_best_estimate_ignores_sets_that_cannot_be_estimated() -> None:
    # The 0-rep attempt at 140 kg must not count as a 140 kg estimate.
    best = best_estimated_one_rep_max([(100, 5), (110, 1), (140, 0)])
    assert best is not None and round(best, 2) == 116.67


def test_best_estimate_of_nothing_is_none() -> None:
    assert best_estimated_one_rep_max([]) is None
    assert best_estimated_one_rep_max([(100, 0)]) is None


@pytest.mark.parametrize(
    ("best_new", "best_before", "expected"),
    [
        (120.0, 110.0, True),
        (110.0, 110.0, False),
        (100.0, 110.0, False),
        (90.0, None, True),
        (None, 80.0, False),
    ],
)
def test_is_personal_record(best_new: float | None, best_before: float | None, expected: bool) -> None:
    assert is_personal_record(best_new, best_before) is expected


def test_volume_is_weight_times_reps_summed() -> None:
    assert volume_kg([(70, 8), (70, 8)]) == 1120
    assert volume_kg([]) == 0


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2024, 1, 1), WEEK_1),
        (date(2024, 1, 3), WEEK_1),
        (date(2024, 1, 7), WEEK_1),
        (date(2024, 1, 8), WEEK_2),
    ],
)
def test_week_start_is_the_monday(day: date, expected: date) -> None:
    assert week_start(day) == expected


def test_weekly_volume_groups_sets_by_week() -> None:
    sets = [(date(2024, 1, 2), 100, 5), (date(2024, 1, 5), 50, 10), (date(2024, 1, 9), 60, 5)]
    assert weekly_volume_kg(sets) == {WEEK_1: 1000, WEEK_2: 300}


def test_average_rpe_by_week() -> None:
    entries = [(date(2024, 1, 1), 8.0), (date(2024, 1, 3), 9.0), (date(2024, 1, 8), 7.0)]
    assert average_rpe_by_week(entries) == {WEEK_1: 8.5, WEEK_2: 7.0}


def test_average_rpe() -> None:
    assert average_rpe([8, 8.5, 9]) == 8.5
    assert average_rpe([7, 7.5, 7.5]) == 7.3  # 7.333… to one decimal
    assert average_rpe([]) is None  # nothing logged: unknown, not 0


MON_WED_FRI = {0, 2, 4}
WEDNESDAY_WEEK_2 = date(2024, 1, 10)


@pytest.mark.parametrize(
    ("start", "end", "trained_today", "expected"),
    [
        # Week 1 in full (Mon, Wed, Fri) plus week 2's Monday; Wednesday is today, not yet trained.
        (WEEK_1, WEDNESDAY_WEEK_2, False, 4),
        # Once a workout is logged today, today's planned session counts too.
        (WEEK_1, WEDNESDAY_WEEK_2, True, 5),
        # A range starting midweek only counts the plan days inside it.
        (date(2024, 1, 3), date(2024, 1, 7), False, 2),
        # Days after today haven't fallen due yet.
        (WEEK_2, date(2024, 1, 14), False, 1),
    ],
)
def test_planned_sessions(start: date, end: date, trained_today: bool, expected: int) -> None:
    assert planned_sessions(MON_WED_FRI, start, end, WEDNESDAY_WEEK_2, trained_today) == expected


def test_planned_sessions_ignores_today_when_it_is_not_a_plan_day() -> None:
    tuesday = date(2024, 1, 9)
    assert planned_sessions(MON_WED_FRI, WEEK_2, tuesday, tuesday, trained_today=True) == 1


def test_no_plan_means_nothing_planned() -> None:
    assert planned_sessions(set(), WEEK_1, WEDNESDAY_WEEK_2, WEDNESDAY_WEEK_2, trained_today=True) == 0


@pytest.mark.parametrize(
    ("done", "planned", "expected"),
    [(3, 3, 100.0), (2, 3, 66.7), (4, 3, 133.3), (0, 3, 0.0), (2, 0, None)],
)
def test_completion_percent(done: int, planned: int, expected: float | None) -> None:
    assert completion_percent(done, planned) == expected


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [(10, 12, 20.0), (10, 8, -20.0), (4.5, 4.5, 0.0), (0, 5, None)],
)
def test_percent_change(before: float, after: float, expected: float | None) -> None:
    assert percent_change(before, after) == expected
