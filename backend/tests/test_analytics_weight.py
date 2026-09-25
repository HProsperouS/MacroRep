from __future__ import annotations

from datetime import date

import pytest

from app.analytics.weight import rate_per_week, trend_on_or_before, trend_series

MON, TUE, WED = date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)


def test_first_reading_seeds_the_trend() -> None:
    assert trend_series([(MON, 80.0)]) == {MON: 80.0}


def test_trend_moves_a_tenth_of_the_way_toward_each_new_reading() -> None:
    # 80 -> 80 + 0.1 * (78 - 80) = 79.8 -> 79.8 + 0.1 * (79.8 - 79.8) = 79.8
    assert trend_series([(MON, 80.0), (TUE, 78.0), (WED, 79.8)]) == {MON: 80.0, TUE: 79.8, WED: 79.8}


def test_readings_are_ordered_by_date_regardless_of_input_order() -> None:
    assert trend_series([(TUE, 78.0), (MON, 80.0)]) == {MON: 80.0, TUE: 79.8}


def test_no_readings_means_no_trend() -> None:
    assert trend_series([]) == {}


def test_trend_on_or_before_picks_the_latest_eligible_date() -> None:
    trends = {MON: 80.0, WED: 79.5}
    assert trend_on_or_before(trends, MON) == 80.0
    assert trend_on_or_before(trends, TUE) == 80.0
    assert trend_on_or_before(trends, date(2024, 1, 31)) == 79.5
    assert trend_on_or_before(trends, date(2023, 12, 31)) is None


@pytest.mark.parametrize(
    ("change_kg", "days", "expected"),
    [(-0.5, 14, -0.25), (1.0, 7, 1.0), (0.3, 30, 0.07), (-1.0, 0, 0.0)],
)
def test_rate_per_week(change_kg: float, days: int, expected: float) -> None:
    assert rate_per_week(change_kg, days) == expected
