"""Food catalog and food-log routes."""

from __future__ import annotations

from datetime import date as date_
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext, get_current_actor
from app.shared.persistence import get_session

from .repository import FoodEntryRepository, FoodRepository
from .schemas import CreateCustomFoodInput, CreateFoodEntryInput, FoodEntryRead, FoodLogResponse, FoodRead
from .service import FoodService

router = APIRouter(prefix="/api", tags=["food"])


def get_food_service(session: Annotated[AsyncSession, Depends(get_session)]) -> FoodService:
    return FoodService(session, FoodRepository(session), FoodEntryRepository(session))


FoodServiceDep = Annotated[FoodService, Depends(get_food_service)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("/food-log", response_model=FoodLogResponse)
async def get_food_log(
    actor: ActorDep, service: FoodServiceDep, date: Annotated[date_, Query()]
) -> FoodLogResponse:
    return await service.get_log(actor, date)


@router.post("/food-log/entries", response_model=FoodEntryRead, status_code=status.HTTP_201_CREATED)
async def add_food_entry(
    payload: CreateFoodEntryInput, actor: ActorDep, service: FoodServiceDep
) -> FoodEntryRead:
    return await service.add_entry(payload, actor)


@router.delete("/food-log/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_food_entry(entry_id: str, actor: ActorDep, service: FoodServiceDep) -> Response:
    await service.remove_entry(entry_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/foods", response_model=list[FoodRead])
async def search_foods(
    actor: ActorDep,
    service: FoodServiceDep,
    q: Annotated[str, Query()] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 8,
) -> list[FoodRead]:
    return await service.search_foods(actor, q, limit)


@router.post("/foods", response_model=FoodRead, status_code=status.HTTP_201_CREATED)
async def create_custom_food(
    payload: CreateCustomFoodInput, actor: ActorDep, service: FoodServiceDep
) -> FoodRead:
    return await service.create_custom_food(payload, actor)
