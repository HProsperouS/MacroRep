"""Progress dashboard routes."""

from __future__ import annotations

from typing import Annotated, get_args

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.coach.repository import CoachRepository
from app.identity.dependencies import ActorContext, get_current_actor
from app.profile.repository import ProfileRepository
from app.shared.persistence import get_session

from .repository import ProgressRepository
from .schemas import DailyCalories, ProgressRange, ProgressResponse
from .service import ProgressService

router = APIRouter(prefix="/api", tags=["progress"])

_VALID_RANGES = set(get_args(ProgressRange))


def get_progress_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ProgressService:
    return ProgressService(ProgressRepository(session), ProfileRepository(session), CoachRepository(session))


ProgressServiceDep = Annotated[ProgressService, Depends(get_progress_service)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("/progress", response_model=ProgressResponse)
async def get_progress(
    actor: ActorDep, service: ProgressServiceDep, range: Annotated[str, Query()] = "3M"
) -> ProgressResponse:
    if range not in _VALID_RANGES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"range must be one of {sorted(_VALID_RANGES)}"
        )
    return await service.get_progress(actor, range)  # type: ignore[arg-type]


@router.get("/nutrition/daily-calories", response_model=list[DailyCalories])
async def get_daily_calories(
    actor: ActorDep, service: ProgressServiceDep, days: Annotated[int, Query(ge=1, le=365)] = 14
) -> list[DailyCalories]:
    return await service.get_daily_calories(actor, days)
