"""Registration, sign-in, refresh-token rotation, and sign-out rules."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.identity.models import User, UserStatus
from app.identity.repository import UserRepository

from .schemas import AccessToken, LoginInput, MeRead, RegisterInput
from .security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite drops timezone info on read, so normalize before comparing."""

    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class AuthService:
    def __init__(self, session: AsyncSession, users: UserRepository, settings: Settings) -> None:
        self.session = session
        self.users = users
        self.settings = settings

    def _issue(self, user: User) -> tuple[AccessToken, str]:
        """Rotate the stored refresh token and mint a matching access token.

        Returns the response body alongside the plain refresh token, which the
        router puts in a cookie — only its digest is ever stored here.
        """

        plain, digest = new_refresh_token()
        user.refresh_token_hash = digest
        user.refresh_expires_at = refresh_expiry(self.settings)
        body = AccessToken(access_token=create_access_token(user.id, self.settings))
        return body, plain

    async def register(self, payload: RegisterInput) -> tuple[AccessToken, str]:
        email = payload.email.strip().lower()
        if await self.users.get_by_email(email) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "That email is already registered")
        user = User(
            name=payload.name.strip(),
            email=email,
            password_hash=hash_password(payload.password),
            status=UserStatus.ACTIVE,
        )
        try:
            await self.users.add(user)
        except IntegrityError as exc:
            # The email's uniqueness is only really enforced here — the check
            # above is a best-effort pre-check, not a lock, so two concurrent
            # registrations for the same address can both pass it. Only that
            # specific violation gets the friendly 409; any other integrity
            # error (a future constraint on this table) re-raises as a 500
            # instead of being mislabeled as a duplicate email.
            await self.session.rollback()
            if "email" not in str(exc.orig).lower():
                raise
            raise HTTPException(status.HTTP_409_CONFLICT, "That email is already registered") from None
        session = self._issue(user)
        await self.session.commit()
        return session

    async def login(self, payload: LoginInput) -> tuple[AccessToken, str]:
        user = await self.users.get_by_email(payload.email.strip().lower())
        # verify_password() always runs, even for an unknown email, against a
        # dummy hash — an `or` short-circuit that skipped it for a missing user
        # would make login() answer faster for "no such email" than for "wrong
        # password", leaking which emails are registered via response timing
        # even though both cases return the same body.
        existing_hash = user.password_hash if user and user.password_hash else DUMMY_PASSWORD_HASH
        password_matches = verify_password(existing_hash, payload.password)
        if user is None or user.password_hash is None or not password_matches:
            # One message for both branches, so a wrong address and a wrong
            # password are indistinguishable to the caller.
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
        if user.status is not UserStatus.ACTIVE:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account is disabled")
        session = self._issue(user)
        await self.session.commit()
        return session

    async def refresh(self, refresh_token: str) -> tuple[AccessToken, str]:
        """Trade a valid refresh token for a new pair, retiring the old one.

        Row-locks the user for the transaction so two concurrent refreshes
        presenting the same cookie can't both read the same stale hash and
        rotate from under each other — the second waits, then correctly sees
        the first's already-rotated hash and is rejected as a replay.
        """

        user = await self.users.get_by_refresh_hash_locked(hash_refresh_token(refresh_token))
        # A rotated-away token no longer matches any row, so replaying an old
        # refresh token lands here as a 401.
        if (
            user is None
            or user.refresh_expires_at is None
            or _as_aware_utc(user.refresh_expires_at) <= datetime.now(UTC)
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token is invalid or expired")
        if user.status is not UserStatus.ACTIVE:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account is disabled")
        session = self._issue(user)
        await self.session.commit()
        return session

    async def logout(self, user_id: str) -> None:
        user = await self.users.get(user_id)
        if user is None:
            return
        user.refresh_token_hash = None
        user.refresh_expires_at = None
        user.touch()
        await self.session.commit()

    async def get_me(self, user_id: str) -> MeRead:
        user = await self.users.get(user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        return MeRead(id=user.id, name=user.name, email=user.email)
