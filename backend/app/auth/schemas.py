"""Registration, sign-in, and token API contracts."""

from __future__ import annotations

from typing import Annotated

from pydantic import EmailStr, Field

from app.shared.schema import CamelModel
from app.shared.validation import MAX_NAME_LENGTH, PlainText

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


class RegisterInput(CamelModel):
    name: PlainText = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


NewPassword = Annotated[str, Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)]
CurrentPassword = Annotated[str, Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)]
Code = Annotated[str, Field(pattern=r"^\d{6}$")]


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


class RequestEmailChangeInput(CamelModel):
    new_email: EmailStr
    # The current password, so a session left signed in can't move the account elsewhere.
    password: CurrentPassword


class ConfirmEmailChangeInput(CamelModel):
    code: Code


class ChangePasswordInput(CamelModel):
    current_password: CurrentPassword
    new_password: NewPassword


class RequestPasswordResetInput(CamelModel):
    email: EmailStr


class ConfirmPasswordResetInput(CamelModel):
    email: EmailStr
    code: Code
    new_password: NewPassword
