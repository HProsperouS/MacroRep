"""User lookups used to resolve the authenticated actor."""

from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: str) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Look up by the normalized (lower-case) address, as stored."""

        return cast(
            "User | None",
            await self.session.scalar(select(User).where(User.email == email)),
        )

    async def get_by_refresh_hash_locked(self, token_hash: str) -> User | None:
        """Resolve the session owner from a presented refresh token's digest,
        holding a row lock until the caller commits (Postgres) so two
        concurrent refreshes presenting the same cookie can't both rotate it
        from the same stale read. A no-op on SQLite, which has no concurrent
        writers to race against in the first place (used only by the
        single-connection test suite).
        """

        return cast(
            "User | None",
            await self.session.scalar(
                select(User).where(User.refresh_token_hash == token_hash).with_for_update()
            ),
        )

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user
