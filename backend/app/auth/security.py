"""Password hashing and the self-issued token pair (access + refresh).

Access tokens are short-lived signed JWTs verified without a database read.
Refresh tokens are opaque random strings: only their SHA-256 digest is stored,
so a leaked database cannot be replayed against the API, and rotating the
stored digest on every refresh gives us server-side revocation.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.core.config import Settings

ACCESS_TOKEN_ALGORITHM = "HS256"
REFRESH_TOKEN_BYTES = 32
REFRESH_TOKEN_HASH_LENGTH = 64  # SHA-256 hex digest, matches the users column

_hasher = PasswordHasher()


class TokenError(Exception):
    """Raised when an access token is malformed, expired, or wrongly signed."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


# A precomputed hash with no corresponding user, verified against whenever the
# presented email doesn't exist. Without this, login() would return 401 for an
# unknown email without ever calling verify_password, while a known email with
# a wrong password runs the (deliberately slow) Argon2 verify first — an
# attacker timing responses could tell the two cases apart even though they
# return an identical body. Hashed once at import time, not per request.
DUMMY_PASSWORD_HASH = hash_password("no-such-user-dummy-password-for-timing-safety")


def verify_password(password_hash: str, password: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
    except VerificationError:
        # Covers both a wrong password and a hash this library cannot read.
        return False
    return True


def create_access_token(user_id: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        },
        settings.jwt_secret_key,
        algorithm=ACCESS_TOKEN_ALGORITHM,
    )


def decode_access_token(token: str, settings: Settings) -> str:
    """Return the user id carried by a valid access token."""

    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[ACCESS_TOKEN_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise TokenError("Token is missing a subject")
    return subject


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    """Return ``(plain_token, hash)``; only the hash is ever persisted."""

    plain = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
    return plain, hash_refresh_token(plain)


def refresh_expiry(settings: Settings) -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
