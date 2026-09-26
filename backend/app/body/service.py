"""Weigh-in recording and editing; the trend itself is computed in ``app.analytics.weight``."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.weight import trend_series
from app.identity.dependencies import ActorContext

from .models import WeighIn
from .repository import WeighInRepository
from .schemas import UpdateWeighInInput, WeighInInput, WeighInRead, WeightPoint


def trend_by_date(weigh_ins: list[WeighIn]) -> dict[date, float]:
    """Trend weight for each stored weigh-in, keyed by its date."""

    return trend_series((row.log_date, float(row.weight_kg)) for row in weigh_ins)


def _date_taken(log_date: date) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, f"There's already a weigh-in on {log_date.isoformat()}")


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

    async def list_weigh_ins(self, actor: ActorContext, start: date, end: date) -> list[WeighInRead]:
        """Weigh-ins between two dates, newest first.

        Trend values are computed over the full history up to ``end``, not just
        the requested window, so they match the weight chart.
        """

        history = await self.repository.list_up_to(actor.actor_id, end)
        trends = trend_by_date(history)
        return [
            WeighInRead(
                id=row.id, date=row.log_date, weight_kg=float(row.weight_kg), trend_kg=trends[row.log_date]
            )
            for row in reversed(history)
            if row.log_date >= start
        ]

    async def update_weigh_in(
        self, weigh_in_id: str, payload: UpdateWeighInInput, actor: ActorContext
    ) -> WeighInRead:
        weigh_in = await self._owned(weigh_in_id, actor)

        if payload.date is not None and payload.date != weigh_in.log_date:
            # One weigh-in per day: moving onto a taken date is a conflict, not a merge.
            if await self.repository.get_on(actor.actor_id, payload.date) is not None:
                raise _date_taken(payload.date)
            weigh_in.log_date = payload.date
        if payload.weight_kg is not None:
            weigh_in.weight_kg = payload.weight_kg
        weigh_in.touch()

        try:
            await self.session.flush()
        except IntegrityError:
            # A concurrent request took the date between the check above and
            # this write; the unique (owner_id, log_date) index caught it.
            await self.session.rollback()
            raise _date_taken(weigh_in.log_date) from None

        history = await self.repository.list_up_to(actor.actor_id, weigh_in.log_date)
        await self.session.commit()
        return WeighInRead(
            id=weigh_in.id,
            date=weigh_in.log_date,
            weight_kg=float(weigh_in.weight_kg),
            trend_kg=trend_by_date(history)[weigh_in.log_date],
        )

    async def delete_weigh_in(self, weigh_in_id: str, actor: ActorContext) -> None:
        await self.repository.delete(await self._owned(weigh_in_id, actor))
        await self.session.commit()

    async def _owned(self, weigh_in_id: str, actor: ActorContext) -> WeighIn:
        weigh_in = await self.repository.get_owned(weigh_in_id, actor.actor_id)
        if weigh_in is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Weigh-in not found")
        return weigh_in
