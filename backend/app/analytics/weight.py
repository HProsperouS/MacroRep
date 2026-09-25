"""Body-weight trend and rate of change.

Trend weight smooths day-to-day scale noise (water, food volume) with an
exponential moving average, the same approach as TrendWeight/Happy Scale: each
new trend point moves a fixed fraction of the way from the previous trend
toward the latest scale reading, instead of reporting the raw scale value.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

TREND_SMOOTHING_FACTOR = 0.1


def trend_series(readings: Iterable[tuple[date, float]]) -> dict[date, float]:
    """Map each weigh-in date to its trend weight (kg), in date order.

    The first reading seeds the trend at its own value. Smoothing is applied
    per reading, not per calendar day, so gaps between weigh-ins don't decay
    the trend on their own.
    """

    trend_by_date: dict[date, float] = {}
    trend: float | None = None
    for day, scale_kg in sorted(readings):
        trend = scale_kg if trend is None else trend + TREND_SMOOTHING_FACTOR * (scale_kg - trend)
        trend_by_date[day] = round(trend, 2)
    return trend_by_date


def trend_on_or_before(trend_by_date: Mapping[date, float], day: date) -> float | None:
    """The latest trend weight recorded on or before ``day``, or None if there is none yet."""

    eligible = [recorded for recorded in trend_by_date if recorded <= day]
    return trend_by_date[max(eligible)] if eligible else None


def rate_per_week(change_kg: float, days: int) -> float:
    """Average weekly change (kg/week) for a change measured over ``days`` days."""

    if days <= 0:
        return 0.0
    return round(change_kg / (days / 7), 3)
