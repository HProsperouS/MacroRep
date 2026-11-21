"""User lookups used to resolve the authenticated actor."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EmailChangeRequest, PasswordResetRequest, User, UserSession


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

    async def add_session(self, user_session: UserSession) -> UserSession:
        self.session.add(user_session)
        await self.session.flush()
        return user_session

    async def get_session(self, session_id: str) -> UserSession | None:
        return await self.session.get(UserSession, session_id)

    async def get_session_by_refresh_hash_locked(self, token_hash: str) -> UserSession | None:
        """The session a presented refresh token's digest belongs to, row-locked until the
        caller commits, so two refreshes presenting the same cookie can't both rotate it from
        the same stale read: the second waits, then finds no match and is refused."""

        return cast(
            "UserSession | None",
            await self.session.scalar(
                select(UserSession).where(UserSession.refresh_token_hash == token_hash).with_for_update()
            ),
        )

    async def delete_session(self, session_id: str) -> None:
        await self.session.execute(delete(UserSession).where(UserSession.id == session_id))

    async def delete_sessions(self, user_id: str, keep: str | None = None) -> None:
        """Sign the user out everywhere, or everywhere but the session ``keep``."""

        statement = delete(UserSession).where(UserSession.user_id == user_id)
        if keep is not None:
            statement = statement.where(UserSession.id != keep)
        await self.session.execute(statement)

    async def prune_sessions(self, user_id: str, keep_latest: int) -> None:
        """Drop the user's expired sessions, and all but the ``keep_latest`` most recently used."""

        mine = UserSession.user_id == user_id
        await self.session.execute(
            delete(UserSession).where(mine, UserSession.expires_at <= datetime.now(UTC))
        )
        newest = (
            select(UserSession.id).where(mine).order_by(UserSession.last_used_utc.desc()).limit(keep_latest)
        )
        await self.session.execute(delete(UserSession).where(mine, UserSession.id.not_in(newest)))

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
