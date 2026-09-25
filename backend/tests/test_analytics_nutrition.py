from __future__ import annotations

from datetime import date

import pytest

from app.analytics.nutrition import average_daily_calories, estimate_expenditure, logging_adherence_percent


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
