"""Food catalog and food-log business rules."""

from __future__ import annotations

from datetime import date as date_

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext

from .models import Food, FoodEntry
from .repository import FoodEntryRepository, FoodRepository
from .schemas import (
    CreateCustomFoodInput,
    CreateFoodEntryInput,
    FoodEntryRead,
    FoodLogResponse,
    FoodRead,
    Nutrition,
)


def _to_food_read(food: Food) -> FoodRead:
    return FoodRead(
        id=food.id,
        name=food.name,
        brand=food.brand,
        serving_size=float(food.serving_size),
        serving_unit=food.serving_unit,
        serving_weight_g=float(food.serving_weight_g) if food.serving_weight_g is not None else None,
        nutrition=Nutrition(
            calories=food.calories, protein=float(food.protein), carbs=float(food.carbs), fat=float(food.fat)
        ),
        fibre_g=float(food.fibre_g) if food.fibre_g is not None else None,
        sugar_g=float(food.sugar_g) if food.sugar_g is not None else None,
        sodium_mg=float(food.sodium_mg) if food.sodium_mg is not None else None,
        source=food.source,
    )


def _to_entry_read(entry: FoodEntry) -> FoodEntryRead:
    return FoodEntryRead(
        id=entry.id,
        meal=entry.meal,
        name=entry.name,
        amount_label=entry.amount_label,
        source=entry.source,
        calories=entry.calories,
        protein=float(entry.protein),
        carbs=float(entry.carbs),
        fat=float(entry.fat),
    )


class FoodService:
    def __init__(self, session: AsyncSession, foods: FoodRepository, entries: FoodEntryRepository) -> None:
        self.session = session
        self.foods = foods
        self.entries = entries

    async def search_foods(self, actor: ActorContext, query: str, limit: int) -> list[FoodRead]:
        rows = await self.foods.search(actor.actor_id, query, limit)
        return [_to_food_read(row) for row in rows]

    async def create_custom_food(self, payload: CreateCustomFoodInput, actor: ActorContext) -> FoodRead:
        food = Food(
            owner_id=actor.actor_id,
            name=payload.name,
            brand=payload.brand,
            serving_size=payload.serving_size,
            serving_unit=payload.serving_unit,
            serving_weight_g=payload.serving_weight_g,
            calories=payload.nutrition.calories,
            protein=payload.nutrition.protein,
            carbs=payload.nutrition.carbs,
            fat=payload.nutrition.fat,
            fibre_g=payload.fibre_g,
            sugar_g=payload.sugar_g,
            sodium_mg=payload.sodium_mg,
        )
        await self.foods.add(food)
        await self.session.commit()
        await self.session.refresh(food)
        return _to_food_read(food)

    async def get_log(self, actor: ActorContext, log_date: date_) -> FoodLogResponse:
        rows = await self.entries.list_for_date(actor.actor_id, log_date)
        return FoodLogResponse(date=log_date, entries=[_to_entry_read(row) for row in rows])

    async def add_entry(self, payload: CreateFoodEntryInput, actor: ActorContext) -> FoodEntryRead:
        entry = FoodEntry(
            owner_id=actor.actor_id,
            log_date=payload.date,
            meal=payload.meal,
            name=payload.name,
            amount_label=payload.amount_label,
            source=payload.source,
            calories=payload.calories,
            protein=payload.protein,
            carbs=payload.carbs,
            fat=payload.fat,
        )
        await self.entries.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return _to_entry_read(entry)

    async def remove_entry(self, entry_id: str, actor: ActorContext) -> None:
        entry = await self.entries.get_owned(entry_id, actor.actor_id)
        if entry is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Food log entry not found")
        await self.entries.remove(entry)
        await self.session.commit()
