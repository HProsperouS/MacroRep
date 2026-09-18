"""Bodyweight routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext, get_current_actor
from app.shared.persistence import get_session

from .repository import WeighInRepository
from .schemas import WeighInInput, WeightPoint
from .service import BodyService

router = APIRouter(prefix="/api", tags=["body"])


def get_body_service(session: Annotated[AsyncSession, Depends(get_session)]) -> BodyService:
    return BodyService(session, WeighInRepository(session))


@router.post("/body/weigh-ins", response_model=WeightPoint, status_code=status.HTTP_201_CREATED)
async def add_weigh_in(
    payload: WeighInInput,
    actor: Annotated[ActorContext, Depends(get_current_actor)],
    service: Annotated[BodyService, Depends(get_body_service)],
) -> WeightPoint:
    return await service.add_weigh_in(payload, actor)
