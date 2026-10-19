"""Owner-scoped profile and nutrition-target persistence."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import NutritionTarget, Profile, TargetSource


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: str) -> Profile | None:
        return await self.session.get(Profile, user_id)

    async def add(self, profile: Profile) -> Profile:
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def current_targets(self, owner_id: str) -> NutritionTarget | None:
        """The newest version of the user's targets, or None if they have none yet."""

        target: NutritionTarget | None = await self.session.scalar(
            select(NutritionTarget)
            .where(NutritionTarget.owner_id == owner_id)
            .order_by(NutritionTarget.version.desc())
            .limit(1)
        )
        return target

    async def target_history(self, owner_id: str) -> list[NutritionTarget]:
        """Every version of the user's targets, oldest first."""

        return list(
            await self.session.scalars(
                select(NutritionTarget)
                .where(NutritionTarget.owner_id == owner_id)
                .order_by(NutritionTarget.version.asc())
            )
        )

    async def calorie_target_versions(self, owner_id: str) -> list[tuple[date, float]]:
        """(effective date, calories) of every version, oldest first, for ``targets_by_date``."""

        return [(row.effective_date, float(row.calories)) for row in await self.target_history(owner_id)]

    async def add_target_version(
        self,
        owner_id: str,
        *,
        previous: NutritionTarget | None,
        calories: int,
        protein: float,
        carbs: float,
        fat: float,
        effective_date: date,
        source: TargetSource,
        proposal_id: str | None = None,
    ) -> NutritionTarget:
        """Record new targets as the version after ``previous``, the version the caller decided on.

        If another change was saved since ``previous`` was read, it already holds that
        version number and the unique (owner_id, version) index rejects this insert, so a
        decision made on outdated targets can't overwrite a newer change.
        """

        target = NutritionTarget(
            owner_id=owner_id,
            version=previous.version + 1 if previous else 1,
            effective_date=effective_date,
            calories=calories,
            protein_g=protein,
            carbs_g=carbs,
            fat_g=fat,
            source=source,
            proposal_id=proposal_id,
        )
        self.session.add(target)
        await self.session.flush()
        return target
