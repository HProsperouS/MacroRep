"""MacroRep user identity and the state backing self-issued auth tokens."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence import Base, TimestampMixin
from app.shared.persistence.mixins import utc_now


class UserStatus(StrEnum):
    ACTIVE = "Active"
    DISABLED = "Disabled"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("uq_users_email", "email", unique=True),)

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: f"USR-{uuid.uuid4().hex[:12].upper()}"
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    # Nullable so an account created through an external identity provider
    # (e.g. Google) can exist without a local password.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Legacy: the one refresh token per user from before ``UserSession``. Nothing reads or
    # writes them any more; they stay for one release so the previous release's tasks keep
    # working while a deploy replaces them, and are dropped in the next (docs/follow-ups.md).
    refresh_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus, name="user_status"), nullable=False, default=UserStatus.ACTIVE
    )


class UserSession(TimestampMixin, Base):
    """One signed-in device: what its refresh token (the cookie) and its access tokens
    (``sid``) belong to.

    Only the token's SHA-256 is stored, so a database leak can't be replayed against the API,
    and it's replaced on every refresh. Deleting the row signs that device out at once: every
    request checks its session still exists (``app.identity.dependencies``). A user keeps at
    most ``MAX_SESSIONS_PER_USER``; signing in past that drops the least recently used.
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("uq_user_sessions_refresh_token_hash", "refresh_token_hash", unique=True),
        Index("ix_user_sessions_user_last_used", "user_id", "last_used_utc"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class EmailChangeRequest(TimestampMixin, Base):
    """A new sign-in email waiting to be confirmed with the code sent to it.

    At most one per user: asking again replaces it. Only the code's HMAC is stored
    (see ``app.auth.security.hash_code``), and it stops working after its expiry or
    too many wrong tries.
    """

    __tablename__ = "email_change_requests"
    __table_args__ = (Index("uq_email_change_requests_user", "user_id", unique=True),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    new_email: Mapped[str] = mapped_column(String(320), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PasswordResetRequest(TimestampMixin, Base):
    """A forgotten password waiting for the code emailed to the account. At most one per
    user; asking again replaces it. Only the code's HMAC is stored, as for email changes."""

    __tablename__ = "password_reset_requests"
    __table_args__ = (Index("uq_password_reset_requests_user", "user_id", unique=True),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
