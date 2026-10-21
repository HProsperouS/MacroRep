"""Food catalog and food-log routes."""

from __future__ import annotations

from datetime import date as date_
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.coach.agents.model import get_coach_model
from app.coach.agents.vision import estimate_photo
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.identity.dependencies import ActorContext, get_current_actor
from app.shared.rate_limit import PHOTOS_PER_USER, count_attempt, user_limiter
from app.shared.validation import MAX_SEARCH_LENGTH

from .repository import FoodEntryRepository, FoodRepository
from .schemas import (
    CreateCustomFoodInput,
    CreateFoodEntryInput,
    FoodEntryRead,
    FoodLogResponse,
    FoodRead,
    PhotoEstimateInput,
    PhotoEstimateRead,
    PhotoItemRead,
    UpdateFoodEntryInput,
)
from .service import FoodService

router = APIRouter(prefix="/api/v1", tags=["food"])


def get_food_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> FoodService:
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


@router.patch("/food-log/entries/{entry_id}", response_model=FoodEntryRead)
async def update_food_entry(
    entry_id: str, payload: UpdateFoodEntryInput, actor: ActorDep, service: FoodServiceDep
) -> FoodEntryRead:
    return await service.update_entry(entry_id, payload, actor)


@router.delete("/food-log/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_food_entry(entry_id: str, actor: ActorDep, service: FoodServiceDep) -> Response:
    await service.remove_entry(entry_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/foods", response_model=list[FoodRead])
async def search_foods(
    actor: ActorDep,
    service: FoodServiceDep,
    q: Annotated[str, Query(max_length=MAX_SEARCH_LENGTH)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 8,
) -> list[FoodRead]:
    return await service.search_foods(actor, q, limit)


@router.get("/foods/{food_id}", response_model=FoodRead)
async def get_food(food_id: str, actor: ActorDep, service: FoodServiceDep) -> FoodRead:
    return await service.get_food(food_id, actor)


@router.post("/foods", response_model=FoodRead, status_code=status.HTTP_201_CREATED)
async def create_custom_food(
    payload: CreateCustomFoodInput, actor: ActorDep, service: FoodServiceDep
) -> FoodRead:
    return await service.create_custom_food(payload, actor)


@router.post("/food/photo-estimates", response_model=PhotoEstimateRead)
async def estimate_meal_photo(
    payload: PhotoEstimateInput, actor: ActorDep, settings: Annotated[Settings, Depends(get_settings)]
) -> PhotoEstimateRead:
    """Estimate the foods in a meal photo, for the user to correct before logging any of them.
    Nothing is logged and the photo isn't kept."""

    key = ("photo", actor.actor_id)
    if settings.rate_limits_enabled:
        count_attempt((key, PHOTOS_PER_USER), reason="That's a lot of photos for now.", counts=user_limiter)
    estimate = await estimate_photo(get_coach_model(), payload.image, actor.actor_id)
    if estimate is None:
        # Our failure, not the user's photo: it doesn't use up one of theirs.
        if settings.rate_limits_enabled:
            user_limiter.undo(key)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The photo couldn't be read just now. Please try again."
        )
    return PhotoEstimateRead(
        items=[PhotoItemRead(**item.model_dump()) for item in estimate.items], note=estimate.note
    )
