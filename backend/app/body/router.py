"""Bodyweight routes."""

from __future__ import annotations

from datetime import date as date_
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext, get_current_actor
from app.shared.persistence import get_session

from .repository import WeighInRepository
from .schemas import UpdateWeighInInput, WeighInInput, WeighInRead, WeightPoint
from .service import BodyService

router = APIRouter(prefix="/api", tags=["body"])

_DEFAULT_LIST_DAYS = 90
_MAX_LIST_DAYS = 366


def get_body_service(session: Annotated[AsyncSession, Depends(get_session)]) -> BodyService:
    return BodyService(session, WeighInRepository(session))


BodyServiceDep = Annotated[BodyService, Depends(get_body_service)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("/body/weigh-ins", response_model=list[WeighInRead])
async def list_weigh_ins(
    actor: ActorDep,
    service: BodyServiceDep,
    date_from: Annotated[date_ | None, Query(alias="from")] = None,
    date_to: Annotated[date_ | None, Query(alias="to")] = None,
) -> list[WeighInRead]:
    """Weigh-ins newest first. Defaults to the last 90 days; at most 366 days per request."""

    end = date_to or date_.today()
    start = date_from or end - timedelta(days=_DEFAULT_LIST_DAYS - 1)
    if start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "'from' must not be after 'to'")
    if (end - start).days + 1 > _MAX_LIST_DAYS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Request at most {_MAX_LIST_DAYS} days at a time"
        )
    return await service.list_weigh_ins(actor, start, end)


@router.post("/body/weigh-ins", response_model=WeightPoint, status_code=status.HTTP_201_CREATED)
async def add_weigh_in(payload: WeighInInput, actor: ActorDep, service: BodyServiceDep) -> WeightPoint:
    return await service.add_weigh_in(payload, actor)


@router.patch(
    "/body/weigh-ins/{weigh_in_id}",
    response_model=WeighInRead,
    responses={409: {"description": "Another weigh-in already exists on the new date."}},
)
async def update_weigh_in(
    weigh_in_id: str, payload: UpdateWeighInInput, actor: ActorDep, service: BodyServiceDep
) -> WeighInRead:
    return await service.update_weigh_in(weigh_in_id, payload, actor)


@router.delete("/body/weigh-ins/{weigh_in_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_weigh_in(weigh_in_id: str, actor: ActorDep, service: BodyServiceDep) -> Response:
    await service.delete_weigh_in(weigh_in_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
