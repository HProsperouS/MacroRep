from __future__ import annotations

from datetime import date

import pytest

from app.analytics.nutrition import (
    DayStatus,
    LoggingCompleteness,
    Nutrients,
    average_daily_calories,
    calories_implausibly_low,
    classify_day,
    day_statuses,
    estimate_expenditure,
    logging_adherence_percent,
    logging_completeness,
    macro_calories,
    scale_nutrients,
    target_adherence_percent,
    target_gap_kcal,
)


def test_macro_calories_use_atwater_factors() -> None:
    assert macro_calories(protein=10, carbs=10, fat=10) == 170  # 40 + 40 + 90


@pytest.mark.parametrize(
    ("calories", "protein", "carbs", "fat", "expected"),
    [
        (150, 1.6, 13, 0, False),  # higher than the macros: alcohol, never flagged
        (200, 100, 0, 0, False),  # exactly half of 400: allowed
        (199, 100, 0, 0, True),  # under half
        (0, 12, 0, 0, False),  # 48 kcal of macros: too small to judge
        (0, 12.5, 0, 0, True),  # 50 kcal of macros and nothing logged
    ],
)
def test_calories_implausibly_low(
    calories: float, protein: float, carbs: float, fat: float, expected: bool
) -> None:
    assert calories_implausibly_low(calories, protein, carbs, fat) is expected


CHICKEN_100G = Nutrients(calories=165, protein=31.0, carbs=0.0, fat=3.6)


def test_scaling_multiplies_every_nutrient() -> None:
    assert scale_nutrients(CHICKEN_100G, 2) == Nutrients(330, 62.0, 0.0, 7.2)


def test_scaling_rounds_halves_up_like_the_frontend_preview() -> None:
    # 165 * 0.5 = 82.5: Python's round() would give 82, the browser's Math.round 83.
    assert scale_nutrients(CHICKEN_100G, 0.5) == Nutrients(83, 15.5, 0.0, 1.8)


def test_scaling_by_zero_servings_is_zero() -> None:
    assert scale_nutrients(CHICKEN_100G, 0) == Nutrients(0, 0.0, 0.0, 0.0)


def test_average_skips_unlogged_days_instead_of_counting_them_as_zero() -> None:
    # Two logged days in a week: the average is over those two, not over seven.
    assert average_daily_calories({date(2024, 1, 1): 1800, date(2024, 1, 3): 2200}) == 2000


def test_average_is_unknown_when_nothing_is_logged() -> None:
    assert average_daily_calories({}) is None


@pytest.mark.parametrize(
    ("logged", "total", "expected"),
    [(7, 7, 100.0), (4, 7, 57.1), (0, 7, 0.0), (10, 7, 100.0), (3, 0, 0.0)],
)
def test_logging_adherence_percent(logged: int, total: int, expected: float) -> None:
    assert logging_adherence_percent(logged, total) == expected


@pytest.mark.parametrize(
    ("calories", "target", "expected"),
    [
        (None, 2000, DayStatus.MISSING),  # nothing logged
        (999, 2000, DayStatus.PARTIAL),  # just under half
        (1000, 2000, DayStatus.COMPLETE),  # exactly half
        (3500, 2000, DayStatus.COMPLETE),  # over target is still a fully logged day
        (0, 2000, DayStatus.PARTIAL),  # a zero-calorie entry (e.g. black coffee) alone
        (300, 0, DayStatus.COMPLETE),  # no target to compare against
    ],
)
def test_classify_day(calories: float | None, target: float, expected: DayStatus) -> None:
    assert classify_day(calories, target) is expected


def test_today_is_in_progress_whatever_was_logged() -> None:
    assert classify_day(None, 2000, in_progress=True) is DayStatus.IN_PROGRESS
    assert classify_day(300, 2000, in_progress=True) is DayStatus.IN_PROGRESS


def test_day_statuses_cover_every_day_and_leave_today_in_progress() -> None:
    today = date(2024, 1, 4)
    logged = {date(2024, 1, 1): 2000, date(2024, 1, 2): 400}
    statuses = day_statuses(logged, date(2024, 1, 1), today, 2000, today)
    assert statuses == {
        date(2024, 1, 1): DayStatus.COMPLETE,
        date(2024, 1, 2): DayStatus.PARTIAL,
        date(2024, 1, 3): DayStatus.MISSING,
        today: DayStatus.IN_PROGRESS,
    }
    assert logging_completeness(statuses.values()) == LoggingCompleteness(complete=1, partial=1, missing=1)


@pytest.mark.parametrize(
    ("logged", "expected"),
    [
        ([2000, 2200, 1800], 100.0),  # both edges of ±10% count
        ([2000, 2201, 1799, 900], 25.0),  # just outside either edge, and a partial day
        ([], None),  # nothing logged: unknown, not 0%
    ],
)
def test_target_adherence_percent(logged: list[float], expected: float | None) -> None:
    assert target_adherence_percent(logged, 2000) == expected


def test_target_adherence_needs_a_target() -> None:
    assert target_adherence_percent([1500], 0) is None


def test_target_gap_counts_partial_days_as_real_intake() -> None:
    # 2000 on target, 1500 is 500 under, a 600 kcal partial day is 1400 under.
    assert target_gap_kcal([2000, 1500, 600], 2000) == -1900
    assert target_gap_kcal([2300], 2000) == 300
    assert target_gap_kcal([], 2000) == 0


def test_losing_weight_means_expenditure_exceeded_intake() -> None:
    # 0.5 kg lost in 7 days = 0.5 * 7700 / 7 = 550 kcal/day deficit.
    assert estimate_expenditure(2000, -0.5, 7) == 2550


def test_gaining_weight_means_intake_exceeded_expenditure() -> None:
    # 0.7 kg gained in 7 days = 770 kcal/day surplus.
    assert estimate_expenditure(2000, 0.7, 7) == 1230


def test_stable_weight_means_expenditure_equals_intake() -> None:
    assert estimate_expenditure(2400, 0.0, 30) == 2400


def test_expenditure_over_no_days_falls_back_to_intake() -> None:
    assert estimate_expenditure(2100, -1.0, 0) == 2100
