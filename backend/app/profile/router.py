"""Profile and nutrition-target routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext, get_current_actor
from app.identity.repository import UserRepository
from app.shared.persistence import get_session

from .repository import ProfileRepository
from .schemas import DailyTargets, ProfileRead, UpdateProfileInput, UpdateTargetsInput
from .service import ProfileService

router = APIRouter(prefix="/api", tags=["profile"])


def get_profile_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ProfileService:
    return ProfileService(session, ProfileRepository(session), UserRepository(session))


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("/profile", response_model=ProfileRead)
async def get_profile(actor: ActorDep, service: ProfileServiceDep) -> ProfileRead:
    return await service.get(actor)


@router.put("/profile", response_model=ProfileRead)
async def update_profile(
    payload: UpdateProfileInput, actor: ActorDep, service: ProfileServiceDep
) -> ProfileRead:
    return await service.update(payload, actor)


@router.get("/nutrition/targets", response_model=DailyTargets)
async def get_targets(actor: ActorDep, service: ProfileServiceDep) -> DailyTargets:
    return await service.get_targets(actor)


@router.put("/nutrition/targets", response_model=DailyTargets)
async def update_targets(
    payload: UpdateTargetsInput, actor: ActorDep, service: ProfileServiceDep
) -> DailyTargets:
    return await service.update_targets(payload, actor)
