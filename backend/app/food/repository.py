"""Owner-scoped food catalog and food-log persistence."""

from __future__ import annotations

from collections.abc import Collection
from datetime import date as date_

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db import escape_like
from app.shared.db import get_owned as _get_owned

from .models import Food, FoodEntry


class FoodRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self, owner_id: str, query: str, limit: int, exclude: Collection[str] = ()
    ) -> list[Food]:
        statement = select(Food).where(or_(Food.owner_id.is_(None), Food.owner_id == owner_id))
        if exclude:
            statement = statement.where(Food.id.not_in(exclude))
        if query:
            pattern = f"%{escape_like(query.strip())}%"
            statement = statement.where(Food.name.ilike(pattern, escape="\\"))
        statement = statement.order_by(Food.name.asc()).limit(limit)
        return list(await self.session.scalars(statement))

    async def recently_eaten(self, owner_id: str, since: date_, limit: int) -> list[Food]:
        """Foods the user ate on or after ``since`` (by the day they're logged against, on the
        owner/date index), the most often eaten first, then the most lately. Quick adds and photo
        entries aren't foods, so they're left out."""

        statement = (
            select(Food)
            .join(FoodEntry, FoodEntry.food_id == Food.id)
            .where(
                FoodEntry.owner_id == owner_id,
                FoodEntry.log_date >= since,
                # Never another user's food, should an entry ever point at one.
                or_(Food.owner_id.is_(None), Food.owner_id == owner_id),
            )
            .group_by(Food.id)
            .order_by(
                func.count(FoodEntry.id).desc(),
                func.max(FoodEntry.log_date).desc(),
                func.max(FoodEntry.created_utc).desc(),
                Food.name,
            )
            .limit(limit)
        )
        return list(await self.session.scalars(statement))

    async def get_visible(self, food_id: str, owner_id: str) -> Food | None:
        """A food by id, if it's in the global catalog or is this user's own custom food."""

        food = await self.session.get(Food, food_id)
        if food is None or (food.owner_id is not None and food.owner_id != owner_id):
            return None
        return food

    async def add(self, food: Food) -> Food:
        self.session.add(food)
        await self.session.flush()
        return food


class FoodEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_date(self, owner_id: str, log_date: date_) -> list[FoodEntry]:
        statement = (
            select(FoodEntry)
            .where(FoodEntry.owner_id == owner_id, FoodEntry.log_date == log_date)
            .order_by(FoodEntry.created_utc.asc())
        )
        return list(await self.session.scalars(statement))

    async def add(self, entry: FoodEntry) -> FoodEntry:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_owned(self, entry_id: str, owner_id: str) -> FoodEntry | None:
        return await _get_owned(self.session, FoodEntry, entry_id, owner_id)

    async def remove(self, entry: FoodEntry) -> None:
        await self.session.delete(entry)
