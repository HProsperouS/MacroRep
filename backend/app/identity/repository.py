"""User lookups used to resolve the authenticated actor."""

from __future__ import annotations

from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EmailChangeRequest, PasswordResetRequest, User


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
        holding a row lock until the caller commits, so two concurrent
        refreshes presenting the same cookie can't both rotate it from the
        same stale read.
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

    async def get_email_change_locked(self, user_id: str) -> EmailChangeRequest | None:
        """The user's pending email change, row-locked until the caller commits, so two
        confirmations at once can't both spend the same attempt."""

        return cast(
            "EmailChangeRequest | None",
            await self.session.scalar(
                select(EmailChangeRequest).where(EmailChangeRequest.user_id == user_id).with_for_update()
            ),
        )

    async def delete_email_change(self, user_id: str) -> None:
        await self.session.execute(delete(EmailChangeRequest).where(EmailChangeRequest.user_id == user_id))

    async def get_password_reset_locked(self, user_id: str) -> PasswordResetRequest | None:
        """The user's pending password reset, row-locked like ``get_email_change_locked``."""

        return cast(
            "PasswordResetRequest | None",
            await self.session.scalar(
                select(PasswordResetRequest).where(PasswordResetRequest.user_id == user_id).with_for_update()
            ),
        )

    async def delete_password_reset(self, user_id: str) -> None:
        await self.session.execute(
            delete(PasswordResetRequest).where(PasswordResetRequest.user_id == user_id)
        )
