"""Registration, sign-in, refresh-token rotation, and sign-out rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.identity.models import EmailChangeRequest, PasswordResetRequest, User, UserStatus
from app.identity.repository import UserRepository
from app.shared.exceptions import Conflict, Forbidden, Invalid, NotFound, Unauthorized

from .passwords import check_new_password
from .schemas import (
    AccessToken,
    ChangePasswordInput,
    ConfirmEmailChangeInput,
    ConfirmPasswordResetInput,
    LoginInput,
    MeRead,
    RegisterInput,
    RequestEmailChangeInput,
    RequestPasswordResetInput,
)
from .security import (
    CODE_TTL,
    DUMMY_PASSWORD_HASH,
    MAX_CODE_ATTEMPTS,
    code_matches,
    create_access_token,
    hash_code,
    hash_password,
    hash_refresh_token,
    new_code,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)

# One message for an unknown email and a wrong password; the sign-in limits count it.
WRONG_CREDENTIALS = "Incorrect email or password"
EMAIL_TAKEN = "That email is already registered"
NO_PENDING_CHANGE = "There's no email change waiting, or its code expired. Ask for a new code."
WRONG_CURRENT_PASSWORD = "Incorrect password"
# One answer for an unknown email, no reset asked for, an expired code and a wrong one.
BAD_RESET_CODE = "That code isn't right or has expired. Check it, or ask for a new one."
CODE_MINUTES = int(CODE_TTL.total_seconds() // 60)


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


def _require_usable(password: str, email: str) -> None:
    reason = check_new_password(password, email)
    if reason is not None:
        raise Invalid(reason)


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
        _require_usable(payload.password, email)
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

    async def request_email_change(self, user_id: str, payload: RequestEmailChangeInput) -> Email:
        """Store a code for the new address and return the email that sends it there; the
        sign-in email changes only once it's confirmed. Asking again replaces the pending
        request and its code.
        """

        # Locked so two requests at once can't both add a pending change.
        user = await self.session.get(User, user_id, with_for_update=True)
        if user is None:
            raise NotFound("User not found")
        if user.password_hash is None or not verify_password(user.password_hash, payload.password):
            raise Forbidden(WRONG_CURRENT_PASSWORD)
        new_email = payload.new_email.strip().lower()
        if new_email == user.email:
            raise Invalid("That's already your email")
        if await self.users.get_by_email(new_email) is not None:
            raise Conflict(EMAIL_TAKEN)

        code = new_code()
        await self.users.delete_email_change(user.id)
        self.session.add(
            EmailChangeRequest(
                user_id=user.id,
                new_email=new_email,
                code_hash=hash_code("email-change", user.id, code, self.settings),
                expires_at=datetime.now(UTC) + CODE_TTL,
                attempts=0,
            )
        )
        await self.session.commit()
        return Email(
            new_email,
            "Your MacroRep verification code",
            f"Hi {user.name},\n\n"
            f"Your code to make {new_email} your MacroRep sign-in email is {code}.\n"
            f"It expires in {CODE_MINUTES} minutes.\n\n"
            "If you didn't ask for this, you can ignore this email.",
        )

    async def confirm_email_change(
        self, user_id: str, payload: ConfirmEmailChangeInput
    ) -> tuple[MeRead, Email]:
        """Switch to the pending email if the code is right. Returns the notice for the old
        address too."""

        pending = await self.users.get_email_change_locked(user_id)
        if pending is None:
            raise Invalid(NO_PENDING_CHANGE)
        if pending.expires_at <= datetime.now(UTC):
            await self.session.delete(pending)
            await self.session.commit()
            raise Invalid(NO_PENDING_CHANGE)
        if not code_matches(pending.code_hash, "email-change", user_id, payload.code, self.settings):
            pending.attempts += 1
            if pending.attempts >= MAX_CODE_ATTEMPTS:
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

        notice = Email(
            old_email,
            "Your MacroRep email was changed",
            f"Hi {user.name},\n\n"
            f"Your MacroRep sign-in email was changed from {old_email} to {user.email}.\n\n"
            "If you didn't do this, contact us straight away.",
        )
        return MeRead(id=user.id, name=user.name, email=user.email), notice

    async def cancel_email_change(self, user_id: str) -> None:
        await self.users.delete_email_change(user_id)
        await self.session.commit()

    async def change_password(
        self, user_id: str, payload: ChangePasswordInput
    ) -> tuple[AccessToken, str, Email]:
        """Set a new password and start a new session here. Other devices are signed out:
        only one refresh token is kept, and this replaces it. Returns the notice to send."""

        user = await self.session.get(User, user_id, with_for_update=True)
        if user is None:
            raise NotFound("User not found")
        if user.password_hash is None or not verify_password(user.password_hash, payload.current_password):
            raise Forbidden(WRONG_CURRENT_PASSWORD)
        if verify_password(user.password_hash, payload.new_password):
            raise Invalid("That's your current password. Pick a new one")
        _require_usable(payload.new_password, user.email)

        user.password_hash = hash_password(payload.new_password)
        user.touch()
        access_token, refresh_token = self._issue(user)
        await self.session.commit()
        notice = Email(
            user.email,
            "Your MacroRep password was changed",
            f"Hi {user.name},\n\n"
            "Your MacroRep password was just changed, and your other devices were signed out.\n\n"
            "If you didn't do this, reset your password straight away from the sign-in page.",
        )
        return access_token, refresh_token, notice

    async def request_password_reset(self, payload: RequestPasswordResetInput) -> Email | None:
        """Store a new reset code for the account, if there is one, and return the email to
        send. The caller answers the same either way and sends it after responding, so the
        answer doesn't tell which emails have accounts."""

        user = await self.users.get_by_email(payload.email.strip().lower())
        if user is None or user.status is not UserStatus.ACTIVE or user.password_hash is None:
            return None
        code = new_code()
        await self.users.delete_password_reset(user.id)
        self.session.add(
            PasswordResetRequest(
                user_id=user.id,
                code_hash=hash_code("password-reset", user.id, code, self.settings),
                expires_at=datetime.now(UTC) + CODE_TTL,
                attempts=0,
            )
        )
        await self.session.commit()
        return Email(
            user.email,
            "Reset your MacroRep password",
            f"Hi {user.name},\n\n"
            f"Your code to reset your MacroRep password is {code}.\n"
            f"It expires in {CODE_MINUTES} minutes.\n\n"
            "If you didn't ask for this, you can ignore this email: your password stays as it is.",
        )

    async def confirm_password_reset(
        self, payload: ConfirmPasswordResetInput
    ) -> tuple[AccessToken, str, Email]:
        """Set the new password if the code is right, and sign in here. Every other device
        is signed out. Returns the notice to send."""

        user = await self.users.get_by_email(payload.email.strip().lower())
        if user is None or user.status is not UserStatus.ACTIVE:
            raise Invalid(BAD_RESET_CODE)
        pending = await self.users.get_password_reset_locked(user.id)
        if pending is None:
            raise Invalid(BAD_RESET_CODE)
        if pending.expires_at <= datetime.now(UTC):
            await self.session.delete(pending)
            await self.session.commit()
            raise Invalid(BAD_RESET_CODE)
        if not code_matches(pending.code_hash, "password-reset", user.id, payload.code, self.settings):
            pending.attempts += 1
            if pending.attempts >= MAX_CODE_ATTEMPTS:
                await self.session.delete(pending)
            await self.session.commit()
            raise Invalid(BAD_RESET_CODE)
        # Checked after the code, so a weak password doesn't spend it: they can try another.
        _require_usable(payload.new_password, user.email)

        user.password_hash = hash_password(payload.new_password)
        user.touch()
        await self.session.delete(pending)
        access_token, refresh_token = self._issue(user)
        await self.session.commit()
        notice = Email(
            user.email,
            "Your MacroRep password was reset",
            f"Hi {user.name},\n\n"
            "Your MacroRep password was reset with a code sent to this email, and your other "
            "devices were signed out.\n\n"
            "If you didn't do this, reset it again now and keep this inbox secure.",
        )
        return access_token, refresh_token, notice
