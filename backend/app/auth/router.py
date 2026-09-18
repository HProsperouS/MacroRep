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
from app.identity.dependencies import ActorContext, get_current_actor
from app.identity.repository import UserRepository
from app.shared.persistence import get_session

from .schemas import AccessToken, LoginInput, MeRead, RegisterInput
from .service import AuthService

router = APIRouter(prefix="/api", tags=["auth"])


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
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


@router.post("/auth/register", response_model=AccessToken, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterInput,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> AccessToken:
    access_token, refresh_token = await service.register(payload)
    _set_refresh_cookie(response, settings, refresh_token)
    return access_token


@router.post("/auth/login", response_model=AccessToken)
async def login(
    payload: LoginInput,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> AccessToken:
    access_token, refresh_token = await service.login(payload)
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
