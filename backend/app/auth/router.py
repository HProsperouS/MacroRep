"""Registration, sign-in, token, and current-user routes.

The access token is returned in the response body and held in memory by the
client. The refresh token is set as an httpOnly cookie scoped to these routes,
so a script injected into the page can neither read it nor ship it elsewhere.
That cookie is what introduces CSRF — something a bearer token is immune to by
construction — which `SameSite` is here to absorb (see ``Settings``).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.identity.dependencies import ActorContext, get_current_actor
from app.identity.repository import UserRepository

from .rate_limit import (
    FAILED_LOGINS_PER_EMAIL,
    FAILED_LOGINS_PER_EMAIL_AND_ADDRESS,
    LOGINS_PER_ADDRESS,
    REGISTRATIONS_PER_ADDRESS,
    Limit,
    limiter,
    too_many_message,
)
from .schemas import AccessToken, LoginInput, MeRead, RegisterInput
from .service import WRONG_CREDENTIALS, AuthService

router = APIRouter(prefix="/api/v1", tags=["auth"])


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(session, UserRepository(session), settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


def _set_refresh_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    # Name, path and domain have to match the ones the cookie was set with, or
    # the browser keeps the original alongside the emptied copy. The remaining
    # attributes only need restating so the expiry is described the same way the
    # original was; `delete_cookie` does not inherit them.
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,
    )


def _address(request: Request) -> str:
    # The connecting address. Behind a proxy that is the proxy's, unless uvicorn is told to
    # trust its X-Forwarded-For (--proxy-headers); see docs/deployment.md.
    return request.client.host if request.client else "unknown"


Check = tuple[tuple[str, str], Limit]


def _count_attempt(*checks: Check) -> None:
    """Refuse with 429 if any check is over its limit; otherwise count this attempt in each.
    Counted before the attempt runs, so attempts sent at once can't all slip under a limit."""

    wait = max((limiter.retry_after(key, limit) or 0 for key, limit in checks), default=0)
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, too_many_message(wait), headers={"Retry-After": str(wait)}
        )
    for key, limit in checks:
        limiter.hit(key, limit)


@router.post("/auth/register", response_model=AccessToken, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterInput,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> AccessToken:
    if settings.auth_rate_limit_enabled:
        _count_attempt((("register", _address(request)), REGISTRATIONS_PER_ADDRESS))
    access_token, refresh_token = await service.register(payload)
    _set_refresh_cookie(response, settings, refresh_token)
    return access_token


@router.post("/auth/login", response_model=AccessToken)
async def login(
    payload: LoginInput,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> AccessToken:
    if not settings.auth_rate_limit_enabled:
        access_token, refresh_token = await service.login(payload)
        _set_refresh_cookie(response, settings, refresh_token)
        return access_token

    address, email = _address(request), payload.email.strip().lower()
    from_here = ("login-failed", f"{email} from {address}")
    anywhere = ("login-failed", email)
    # Every attempt counts as a wrong password until it proves otherwise, and a locked
    # account is refused before its password is checked, even a correct one.
    _count_attempt(
        (("login", address), LOGINS_PER_ADDRESS),
        (from_here, FAILED_LOGINS_PER_EMAIL_AND_ADDRESS),
        (anywhere, FAILED_LOGINS_PER_EMAIL),
    )
    try:
        access_token, refresh_token = await service.login(payload)
    except Exception as error:
        # Anything but a wrong password (a disabled account, a server error) wasn't a guess.
        if not (isinstance(error, HTTPException) and error.detail == WRONG_CREDENTIALS):
            limiter.undo(from_here)
            limiter.undo(anywhere)
        raise
    # The owner from here starts afresh; the account-wide count keeps bounding guesses elsewhere.
    limiter.clear(from_here)
    limiter.undo(anywhere)
    _set_refresh_cookie(response, settings, refresh_token)
    return access_token


@router.post("/auth/refresh", response_model=AccessToken)
async def refresh(
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> AccessToken:
    """Trade the refresh cookie for a fresh access token, rotating the cookie."""

    presented = request.cookies.get(settings.refresh_cookie_name)
    if not presented:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token was presented")
    access_token, refresh_token = await service.refresh(presented)
    _set_refresh_cookie(response, settings, refresh_token)
    return access_token


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    actor: ActorDep,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> None:
    await service.logout(actor.actor_id)
    _clear_refresh_cookie(response, settings)


@router.get("/users/me", response_model=MeRead)
async def get_me(actor: ActorDep, service: AuthServiceDep) -> MeRead:
    return await service.get_me(actor.actor_id)
