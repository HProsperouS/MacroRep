"""Weigh-in recording; the trend itself is computed in ``app.analytics.weight``."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.weight import trend_series
from app.identity.dependencies import ActorContext

from .models import WeighIn
from .repository import WeighInRepository
from .schemas import WeighInInput, WeightPoint


def trend_by_date(weigh_ins: list[WeighIn]) -> dict[date, float]:
    """Trend weight for each stored weigh-in, keyed by its date."""

    return trend_series((row.log_date, float(row.weight_kg)) for row in weigh_ins)


class BodyService:
    def __init__(self, session: AsyncSession, repository: WeighInRepository) -> None:
        self.session = session
        self.repository = repository

    async def add_weigh_in(self, payload: WeighInInput, actor: ActorContext) -> WeightPoint:
        await self.repository.upsert(actor.actor_id, payload.date, payload.weight_kg)
        history = await self.repository.list_up_to(actor.actor_id, payload.date)
        trends = trend_by_date(history)
        await self.session.commit()
        return WeightPoint(date=payload.date, scale_kg=payload.weight_kg, trend_kg=trends[payload.date])
