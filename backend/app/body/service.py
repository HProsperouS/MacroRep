"""Weigh-in recording and trend-weight calculation.

Trend weight smooths day-to-day scale noise with an exponential moving
average (the same approach as Trendweight/Happy Scale): each new trend point
is nudged toward the latest scale reading by a fixed smoothing factor, rather
than reported as the raw (noisy) scale value.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext

from .models import WeighIn
from .repository import WeighInRepository
from .schemas import WeighInInput, WeightPoint

TREND_SMOOTHING_FACTOR = 0.1


def compute_trend_series(weigh_ins: list[WeighIn]) -> dict[str, float]:
    """Map each weigh-in's date (ISO string) to its trend weight, in date order."""

    trend_by_date: dict[str, float] = {}
    trend: float | None = None
    for row in weigh_ins:
        scale = float(row.weight_kg)
        trend = scale if trend is None else trend + TREND_SMOOTHING_FACTOR * (scale - trend)
        trend_by_date[row.log_date.isoformat()] = round(trend, 2)
    return trend_by_date


class BodyService:
    def __init__(self, session: AsyncSession, repository: WeighInRepository) -> None:
        self.session = session
        self.repository = repository

    async def add_weigh_in(self, payload: WeighInInput, actor: ActorContext) -> WeightPoint:
        await self.repository.upsert(actor.actor_id, payload.date, payload.weight_kg)
        history = await self.repository.list_up_to(actor.actor_id, payload.date)
        trend_series = compute_trend_series(history)
        await self.session.commit()
        return WeightPoint(
            date=payload.date, scale_kg=payload.weight_kg, trend_kg=trend_series[payload.date.isoformat()]
        )
