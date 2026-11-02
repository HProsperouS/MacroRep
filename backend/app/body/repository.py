"""Owner-scoped weigh-in persistence."""

from __future__ import annotations

from datetime import date as date_
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db import get_owned as _get_owned
from app.shared.persistence.mixins import utc_now

from .models import WeighIn


class WeighInRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_up_to(self, owner_id: str, up_to: date_) -> list[WeighIn]:
        statement = (
            select(WeighIn)
            .where(WeighIn.owner_id == owner_id, WeighIn.log_date <= up_to)
            .order_by(WeighIn.log_date.asc())
        )
        return list(await self.session.scalars(statement))

    async def get_owned(self, weigh_in_id: str, owner_id: str) -> WeighIn | None:
        return await _get_owned(self.session, WeighIn, weigh_in_id, owner_id)

    async def get_on(self, owner_id: str, log_date: date_) -> WeighIn | None:
        return cast(
            "WeighIn | None",
            await self.session.scalar(
                select(WeighIn).where(WeighIn.owner_id == owner_id, WeighIn.log_date == log_date)
            ),
        )

    async def latest(self, owner_id: str, up_to: date_) -> WeighIn | None:
        """The most recent weigh-in on or before ``up_to``."""

        return cast(
            "WeighIn | None",
            await self.session.scalar(
                select(WeighIn)
                .where(WeighIn.owner_id == owner_id, WeighIn.log_date <= up_to)
                .order_by(WeighIn.log_date.desc())
                .limit(1)
            ),
        )

    async def delete(self, weigh_in: WeighIn) -> None:
        await self.session.delete(weigh_in)

    async def upsert(self, owner_id: str, log_date: date_, weight_kg: float) -> None:
        """Record the day's weigh-in, replacing one already there (one a day).

        One INSERT ... ON CONFLICT UPDATE, not a SELECT then a write: two
        requests saving the same day at once can't both miss the other's row.
        """

        statement = (
            pg_insert(WeighIn)
            .values(owner_id=owner_id, log_date=log_date, weight_kg=weight_kg)
            .on_conflict_do_update(
                index_elements=[WeighIn.owner_id, WeighIn.log_date],
                set_={"weight_kg": weight_kg, "updated_utc": utc_now()},
            )
        )
        await self.session.execute(statement)
