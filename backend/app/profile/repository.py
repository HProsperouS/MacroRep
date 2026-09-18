"""Owner-scoped profile persistence."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .models import Profile


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: str) -> Profile | None:
        return await self.session.get(Profile, user_id)

    async def add(self, profile: Profile) -> Profile:
        self.session.add(profile)
        await self.session.flush()
        return profile
