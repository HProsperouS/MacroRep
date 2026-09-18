"""Authentication dependency.

Resolves the caller's ``ActorContext`` from a self-issued access token (see
``app.auth.security``) when one is presented, falling back to the
`X-Preview-Actor-Id` local-development seam otherwise. Preview auth is itself
forbidden once `APP_ENV=prod` (see `Settings.reject_debug_in_production`), so
production can only ever authenticate through a verified access token.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import TokenError, decode_access_token
from app.core.config import Settings, get_settings
from app.shared.persistence import get_session

from .models import User, UserStatus
from .repository import UserRepository


class ActorContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    actor_id: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)

    @property
    def user_id(self) -> str:
        return self.actor_id


def _actor_from_user(user: User) -> ActorContext:
    return ActorContext(actor_id=user.id, display_name=user.name)


async def get_current_actor(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    preview_actor_id: Annotated[
        str | None, Header(alias="X-Preview-Actor-Id", min_length=1, max_length=255)
    ] = None,
) -> ActorContext:
    """Resolve the authenticated actor from a self-issued access token, or the
    local preview header when preview auth is enabled for this environment.
    """

    if authorization and authorization.lower().startswith("bearer "):
        try:
            user_id = decode_access_token(authorization[len("Bearer ") :].strip(), settings)
        except TokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
            ) from exc
        user = await UserRepository(session).get(user_id)
        if user is None or user.status is not UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user is unknown or inactive",
            )
        return _actor_from_user(user)

    if not settings.preview_auth_enabled or preview_actor_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated actor context is required"
        )
    user = await session.get(User, preview_actor_id)
    if user is None or user.status is not UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Preview actor is unknown or inactive"
        )
    return _actor_from_user(user)
