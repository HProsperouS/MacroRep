"""Registration, sign-in, refresh-token rotation, and sign-out rules."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.identity.models import EmailChangeRequest, User, UserStatus
from app.identity.repository import UserRepository
from app.shared.exceptions import Conflict, Invalid, NotFound, Unauthorized, Unavailable
from app.shared.mail import LogMailer, Mailer, MailError

from .schemas import (
    AccessToken,
    ConfirmEmailChangeInput,
    LoginInput,
    MeRead,
    RegisterInput,
    RequestEmailChangeInput,
)
from .security import (
    DUMMY_PASSWORD_HASH,
    EMAIL_CODE_TTL,
    MAX_EMAIL_CODE_ATTEMPTS,
    create_access_token,
    email_code_matches,
    hash_email_code,
    hash_password,
    hash_refresh_token,
    new_email_code,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)

logger = logging.getLogger(__name__)

# One message for an unknown email and a wrong password; the sign-in limits count it.
WRONG_CREDENTIALS = "Incorrect email or password"
EMAIL_TAKEN = "That email is already registered"
NO_PENDING_CHANGE = "There's no email change waiting, or its code expired. Ask for a new code."


class AuthService:
    def __init__(
        self, session: AsyncSession, users: UserRepository, settings: Settings, mailer: Mailer | None = None
    ) -> None:
        self.session = session
        self.users = users
        self.settings = settings
        self.mailer = mailer or LogMailer()

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
            raise Conflict(EMAIL_TAKEN)
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
            raise Conflict(EMAIL_TAKEN) from None
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
            raise Unauthorized(WRONG_CREDENTIALS)
        if user.status is not UserStatus.ACTIVE:
            raise Unauthorized("This account is disabled")
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
        if user is None or user.refresh_expires_at is None or user.refresh_expires_at <= datetime.now(UTC):
            raise Unauthorized("Refresh token is invalid or expired")
        if user.status is not UserStatus.ACTIVE:
            raise Unauthorized("This account is disabled")
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
            raise NotFound("User not found")
        return MeRead(id=user.id, name=user.name, email=user.email)

    async def request_email_change(self, user_id: str, payload: RequestEmailChangeInput) -> None:
        """Send a code to the new address; the email changes only once it's confirmed.

        Asking again replaces the pending request and its code. Nothing is stored if the
        email can't be sent.
        """

        # Locked so two requests at once can't both add a pending change.
        user = await self.session.get(User, user_id, with_for_update=True)
        if user is None:
            raise NotFound("User not found")
        if user.password_hash is None or not verify_password(user.password_hash, payload.password):
            raise Unauthorized("Incorrect password")
        new_email = payload.new_email.strip().lower()
        if new_email == user.email:
            raise Invalid("That's already your email")
        if await self.users.get_by_email(new_email) is not None:
            raise Conflict(EMAIL_TAKEN)

        code = new_email_code()
        await self.users.delete_email_change(user.id)
        self.session.add(
            EmailChangeRequest(
                user_id=user.id,
                new_email=new_email,
                code_hash=hash_email_code(user.id, code, self.settings),
                expires_at=datetime.now(UTC) + EMAIL_CODE_TTL,
                attempts=0,
            )
        )
        await self.session.flush()
        minutes = int(EMAIL_CODE_TTL.total_seconds() // 60)
        try:
            await self.mailer.send(
                new_email,
                "Your MacroRep verification code",
                f"Hi {user.name},\n\n"
                f"Your code to make {new_email} your MacroRep sign-in email is {code}.\n"
                f"It expires in {minutes} minutes.\n\n"
                "If you didn't ask for this, you can ignore this email.",
            )
        except MailError:
            await self.session.rollback()
            logger.exception("Couldn't send an email-change code for user %s", user_id)
            raise Unavailable("Couldn't send the code just now. Try again.") from None
        await self.session.commit()

    async def confirm_email_change(self, user_id: str, payload: ConfirmEmailChangeInput) -> MeRead:
        """Switch to the pending email if the code is right, then tell the old address."""

        pending = await self.users.get_email_change_locked(user_id)
        if pending is None:
            raise Invalid(NO_PENDING_CHANGE)
        if pending.expires_at <= datetime.now(UTC):
            await self.session.delete(pending)
            await self.session.commit()
            raise Invalid(NO_PENDING_CHANGE)
        if not email_code_matches(pending.code_hash, user_id, payload.code, self.settings):
            pending.attempts += 1
            if pending.attempts >= MAX_EMAIL_CODE_ATTEMPTS:
                await self.session.delete(pending)
                await self.session.commit()
                raise Invalid("Too many wrong codes. Ask for a new code.")
            await self.session.commit()
            raise Invalid("That code isn't right")

        user = await self.users.get(user_id)
        if user is None:
            raise NotFound("User not found")
        old_email, user.email = user.email, pending.new_email
        user.touch()
        await self.session.delete(pending)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            # Someone registered the address after the code was sent.
            await self.session.rollback()
            if "email" not in str(exc.orig).lower():
                raise
            raise Conflict(EMAIL_TAKEN) from None

        try:
            await self.mailer.send(
                old_email,
                "Your MacroRep email was changed",
                f"Hi {user.name},\n\n"
                f"Your MacroRep sign-in email was changed from {old_email} to {user.email}.\n\n"
                "If you didn't do this, contact us straight away.",
            )
        except MailError:
            # The change is made; a missing notice shouldn't undo it or fail the request.
            logger.exception("Couldn't send the email-changed notice for user %s", user_id)
        return MeRead(id=user.id, name=user.name, email=user.email)

    async def cancel_email_change(self, user_id: str) -> None:
        await self.users.delete_email_change(user_id)
        await self.session.commit()
