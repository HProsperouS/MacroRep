"""Food catalog and food-log business rules."""

from __future__ import annotations

from datetime import date as date_
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.nutrition import Nutrients, scale_nutrients
from app.identity.dependencies import ActorContext
from app.shared.validation import ensure_plausible_calories

from .models import Food, FoodEntry, FoodSource
from .repository import FoodEntryRepository, FoodRepository
from .schemas import (
    CreateCustomFoodInput,
    CreateFoodEntryInput,
    FoodEntryRead,
    FoodLogResponse,
    FoodRead,
    Nutrition,
    QuantityUnit,
    UpdateFoodEntryInput,
)


def _format_amount(value: float, max_decimals: int) -> str:
    """1500.0 -> "1,500"; 0.75 -> "0.8" at one decimal: matches the frontend's number format."""

    text = f"{value:,.{max_decimals}f}"
    return text.rstrip("0").rstrip(".") if max_decimals else text


def _grams_per_serving(food: Food) -> float | None:
    if food.serving_weight_g is not None:
        return float(food.serving_weight_g)
    if food.serving_unit == "g":
        return float(food.serving_size)
    return None


def _servings(food: Food, quantity: float, unit: QuantityUnit) -> float:
    """Convert a logged quantity to a number of the food's servings."""

    if unit == "serving":
        return quantity
    grams_per_serving = _grams_per_serving(food)
    if grams_per_serving is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"{food.name} has no serving weight, so it can't be logged in grams",
        )
    return quantity / grams_per_serving


def _amount_label(food: Food, quantity: float, unit: QuantityUnit) -> str:
    if unit == "g":
        return f"{_format_amount(quantity, 1)} g"
    label = f"{_format_amount(quantity * float(food.serving_size), 1)} {food.serving_unit}"
    if food.serving_weight_g is not None and food.serving_unit != "g":
        label += f" · {_format_amount(quantity * float(food.serving_weight_g), 0)} g"
    return label


def _apply_food_quantity(entry: FoodEntry, food: Food, quantity: float, unit: QuantityUnit) -> None:
    """Derive an entry's name, amount label, and nutrition from a saved food and a quantity."""

    per_serving = Nutrients(food.calories, float(food.protein), float(food.carbs), float(food.fat))
    scaled = scale_nutrients(per_serving, _servings(food, quantity, unit))
    entry.food_id = food.id
    entry.quantity = quantity
    entry.quantity_unit = unit
    entry.name = food.name
    entry.amount_label = _amount_label(food, quantity, unit)
    entry.source = food.source
    entry.calories, entry.protein, entry.carbs, entry.fat = scaled


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
        food_id=entry.food_id,
        quantity=float(entry.quantity) if entry.quantity is not None else None,
        quantity_unit=cast("QuantityUnit | None", entry.quantity_unit),
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

    async def get_food(self, food_id: str, actor: ActorContext) -> FoodRead:
        return _to_food_read(await self._visible_food(food_id, actor))

    async def _visible_food(self, food_id: str, actor: ActorContext) -> Food:
        food = await self.foods.get_visible(food_id, actor.actor_id)
        if food is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Food not found")
        return food

    async def add_entry(self, payload: CreateFoodEntryInput, actor: ActorContext) -> FoodEntryRead:
        entry = FoodEntry(owner_id=actor.actor_id, log_date=payload.date, meal=payload.meal)
        if payload.food_id is not None:
            food = await self._visible_food(payload.food_id, actor)
            _apply_food_quantity(entry, food, cast(float, payload.quantity), payload.quantity_unit)
        else:
            # The schema guarantees every entered value is present without a food_id.
            entry.name = cast(str, payload.name)
            entry.amount_label = cast(str, payload.amount_label)
            entry.source = cast(FoodSource, payload.source)
            entry.calories = cast(int, payload.calories)
            entry.protein = cast(float, payload.protein)
            entry.carbs = cast(float, payload.carbs)
            entry.fat = cast(float, payload.fat)
        await self.entries.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return _to_entry_read(entry)

    async def update_entry(
        self, entry_id: str, payload: UpdateFoodEntryInput, actor: ActorContext
    ) -> FoodEntryRead:
        entry = await self.entries.get_owned(entry_id, actor.actor_id)
        if entry is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Food log entry not found")

        if entry.food_id is not None:
            if payload.entered_values():
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "This entry comes from a saved food: change its quantity and the nutrition follows.",
                )
            if payload.changes_quantity():
                food = await self._visible_food(entry.food_id, actor)
                quantity = (
                    payload.quantity if payload.quantity is not None else float(cast(float, entry.quantity))
                )
                unit = payload.quantity_unit or cast(QuantityUnit, entry.quantity_unit)
                _apply_food_quantity(entry, food, quantity, unit)
        else:
            if payload.changes_quantity():
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "This entry has no saved food to scale: edit its calories and macros instead.",
                )
            for field, value in payload.entered_values().items():
                setattr(entry, field, value)
            # Checked on the merged result: an edit may change calories or one macro alone.
            try:
                ensure_plausible_calories(
                    entry.calories, float(entry.protein), float(entry.carbs), float(entry.fat)
                )
            except ValueError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None

        if payload.date is not None:
            entry.log_date = payload.date
        if payload.meal is not None:
            entry.meal = payload.meal
        entry.touch()
        await self.session.commit()
        await self.session.refresh(entry)
        return _to_entry_read(entry)

    async def remove_entry(self, entry_id: str, actor: ActorContext) -> None:
        entry = await self.entries.get_owned(entry_id, actor.actor_id)
        if entry is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Food log entry not found")
        await self.entries.remove(entry)
        await self.session.commit()
