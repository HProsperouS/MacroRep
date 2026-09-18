"""Food catalog and food-log API contracts."""

from __future__ import annotations

from datetime import date as date_

from pydantic import Field, field_validator

from app.shared.schema import CamelModel, validate_choice

from .models import MEAL_TYPES, SERVING_UNITS, FoodSource


class Nutrition(CamelModel):
    calories: int = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)


class FoodRead(CamelModel):
    id: str
    name: str
    brand: str | None = None
    serving_size: float
    serving_unit: str
    serving_weight_g: float | None = None
    nutrition: Nutrition
    fibre_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None
    source: FoodSource


class CreateCustomFoodInput(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    brand: str | None = None
    serving_size: float = Field(gt=0)
    serving_unit: str
    serving_weight_g: float | None = Field(default=None, gt=0)
    nutrition: Nutrition
    fibre_g: float | None = Field(default=None, ge=0)
    sugar_g: float | None = Field(default=None, ge=0)
    sodium_mg: float | None = Field(default=None, ge=0)

    @field_validator("serving_unit")
    @classmethod
    def check_serving_unit(cls, value: str) -> str:
        return validate_choice(value, SERVING_UNITS, "servingUnit")


class FoodEntryRead(CamelModel):
    id: str
    meal: str
    name: str
    amount_label: str
    source: FoodSource
    calories: int
    protein: float
    carbs: float
    fat: float


class CreateFoodEntryInput(CamelModel):
    date: date_
    meal: str
    name: str = Field(min_length=1, max_length=255)
    amount_label: str = Field(min_length=1, max_length=64)
    source: FoodSource
    calories: int = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)

    @field_validator("meal")
    @classmethod
    def check_meal(cls, value: str) -> str:
        return validate_choice(value, MEAL_TYPES, "meal")


class FoodLogResponse(CamelModel):
    date: date_
    entries: list[FoodEntryRead]
