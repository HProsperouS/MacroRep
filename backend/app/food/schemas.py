"""Food catalog and food-log API contracts."""

from __future__ import annotations

from datetime import date as date_
from typing import Literal

from pydantic import Field, field_validator, model_validator

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


QuantityUnit = Literal["serving", "g"]

# Upper bound for a logged amount, in servings or grams.
_MAX_QUANTITY = 5000

# Fields a quick add supplies itself; a saved food's entry derives them instead.
_ENTERED_VALUE_FIELDS = ("name", "amount_label", "calories", "protein", "carbs", "fat")


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
    # Set when logged from a saved food; editing the quantity re-scales the nutrition.
    food_id: str | None = None
    quantity: float | None = None
    quantity_unit: QuantityUnit | None = None


class CreateFoodEntryInput(CamelModel):
    """Either a saved food and a quantity, or a quick add's values as entered.

    For a saved food the server derives the name, amount label, and nutrition
    from the food, so they must not be sent.
    """

    date: date_
    meal: str
    food_id: str | None = None
    quantity: float | None = Field(default=None, gt=0, le=_MAX_QUANTITY)
    quantity_unit: QuantityUnit = "serving"
    name: str | None = Field(default=None, min_length=1, max_length=255)
    amount_label: str | None = Field(default=None, min_length=1, max_length=64)
    source: FoodSource | None = None
    calories: int | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    carbs: float | None = Field(default=None, ge=0)
    fat: float | None = Field(default=None, ge=0)

    @field_validator("meal")
    @classmethod
    def check_meal(cls, value: str) -> str:
        return validate_choice(value, MEAL_TYPES, "meal")

    @model_validator(mode="after")
    def check_one_kind_of_entry(self) -> CreateFoodEntryInput:
        if self.food_id is not None:
            if self.quantity is None:
                raise ValueError("quantity is required when logging a saved food")
            sent = [field for field in (*_ENTERED_VALUE_FIELDS, "source") if getattr(self, field) is not None]
            if sent:
                raise ValueError(f"these are derived from the food and must not be sent: {', '.join(sent)}")
        else:
            missing = [field for field in (*_ENTERED_VALUE_FIELDS, "source") if getattr(self, field) is None]
            if missing:
                raise ValueError(f"required without a foodId: {', '.join(missing)}")
        return self


class UpdateFoodEntryInput(CamelModel):
    """Fields to change; anything omitted is left as it is.

    ``date`` and ``meal`` apply to every entry. A saved food's entry changes
    its ``quantity``/``quantity_unit`` (nutrition is re-scaled from the food);
    a quick add changes its values directly.
    """

    date: date_ | None = None
    meal: str | None = None
    quantity: float | None = Field(default=None, gt=0, le=_MAX_QUANTITY)
    quantity_unit: QuantityUnit | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    amount_label: str | None = Field(default=None, min_length=1, max_length=64)
    calories: int | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    carbs: float | None = Field(default=None, ge=0)
    fat: float | None = Field(default=None, ge=0)

    @field_validator("meal")
    @classmethod
    def check_meal(cls, value: str | None) -> str | None:
        return None if value is None else validate_choice(value, MEAL_TYPES, "meal")

    def entered_values(self) -> dict[str, object]:
        return {
            field: getattr(self, field) for field in _ENTERED_VALUE_FIELDS if getattr(self, field) is not None
        }

    def changes_quantity(self) -> bool:
        return self.quantity is not None or self.quantity_unit is not None


class FoodLogResponse(CamelModel):
    date: date_
    entries: list[FoodEntryRead]
