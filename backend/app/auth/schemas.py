"""Registration, sign-in, and token API contracts."""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.shared.schema import CamelModel
from app.shared.validation import MAX_NAME_LENGTH, PlainText

MIN_PASSWORD_LENGTH = 8


class RegisterInput(CamelModel):
    name: PlainText = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


class LoginInput(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AccessToken(CamelModel):
    """The short-lived token a client attaches to each request.

    The matching refresh token is deliberately absent: it is delivered as an
    httpOnly cookie (see ``app.auth.router``) so a script injected into the page
    cannot read it. It is also not accepted as input for the same reason — the
    refresh endpoint reads the cookie instead.
    """

    access_token: str


class MeRead(CamelModel):
    id: str
    name: str
    email: str
