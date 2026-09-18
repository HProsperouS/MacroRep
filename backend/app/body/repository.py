"""Owner-scoped weigh-in persistence."""

from __future__ import annotations

from datetime import date as date_

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def upsert(self, owner_id: str, log_date: date_, weight_kg: float) -> WeighIn:
        existing = await self.session.scalar(
            select(WeighIn).where(WeighIn.owner_id == owner_id, WeighIn.log_date == log_date)
        )
        if existing is not None:
            existing.weight_kg = weight_kg
            existing.touch()
            return existing
        row = WeighIn(owner_id=owner_id, log_date=log_date, weight_kg=weight_kg)
        self.session.add(row)
        await self.session.flush()
        return row
