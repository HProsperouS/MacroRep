"""Profile and nutrition-target routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.body.repository import WeighInRepository
from app.core.database import get_db_session
from app.identity.dependencies import ActorContext, get_current_actor
from app.identity.repository import UserRepository

from .repository import ProfileRepository
from .schemas import (
    DailyTargets,
    EstimateTargetsInput,
    OnboardingInput,
    ProfileRead,
    TargetEstimateRead,
    TargetVersionRead,
    TimezoneInput,
    UpdateProfileInput,
    UpdateTargetsInput,
)
from .service import ProfileService

router = APIRouter(prefix="/api/v1", tags=["profile"])


def get_profile_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> ProfileService:
    return ProfileService(
        session, ProfileRepository(session), UserRepository(session), WeighInRepository(session)
    )


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


@router.post(
    "/profile/onboarding",
    response_model=ProfileRead,
    responses={409: {"description": "The sign-up guide was already finished."}},
)
async def complete_onboarding(
    payload: OnboardingInput, actor: ActorDep, service: ProfileServiceDep
) -> ProfileRead:
    """Finish the sign-up guide: the profile, today's weight and the starting daily targets."""

    return await service.complete_onboarding(payload, actor)


@router.put("/profile/timezone", response_model=ProfileRead)
async def set_timezone(payload: TimezoneInput, actor: ActorDep, service: ProfileServiceDep) -> ProfileRead:
    """Record the browser's IANA timezone, which decides the user's calendar days."""

    return await service.set_timezone(payload, actor)


@router.get("/nutrition/targets", response_model=DailyTargets)
async def get_targets(actor: ActorDep, service: ProfileServiceDep) -> DailyTargets:
    return await service.get_targets(actor)


@router.put("/nutrition/targets", response_model=DailyTargets)
async def update_targets(
    payload: UpdateTargetsInput, actor: ActorDep, service: ProfileServiceDep
) -> DailyTargets:
    return await service.update_targets(payload, actor)


@router.post("/nutrition/targets/estimate", response_model=TargetEstimateRead)
async def estimate_targets(
    payload: EstimateTargetsInput, actor: ActorDep, service: ProfileServiceDep
) -> TargetEstimateRead:
    """Estimate starting targets from details not saved yet (the sign-up guide). Saves nothing."""

    return await service.estimate_targets(payload, actor)


@router.get(
    "/nutrition/targets/estimate",
    response_model=TargetEstimateRead,
    responses={409: {"description": "The profile or a weigh-in the estimate needs is missing."}},
)
async def estimate_targets_from_profile(actor: ActorDep, service: ProfileServiceDep) -> TargetEstimateRead:
    """Estimate targets from the saved profile and the latest weigh-in. Saves nothing."""

    return await service.estimate_targets_from_profile(actor)


@router.get("/nutrition/targets/history", response_model=list[TargetVersionRead])
async def get_target_history(actor: ActorDep, service: ProfileServiceDep) -> list[TargetVersionRead]:
    """The latest ``MAX_TARGET_HISTORY`` versions of the daily targets, newest first, with the
    day each took effect."""

    return await service.target_history(actor)
