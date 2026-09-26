"""Food catalog and food-log API contracts."""

from __future__ import annotations

from datetime import date as date_
from typing import Literal, cast

from pydantic import Field, field_validator, model_validator

from app.shared.schema import CamelModel, validate_choice
from app.shared.validation import (
    MAX_CALORIES,
    MAX_FIBRE_G,
    MAX_LABEL_LENGTH,
    MAX_MACRO_G,
    MAX_NAME_LENGTH,
    MAX_SERVING_SIZE,
    MAX_SODIUM_MG,
    MAX_SUGAR_G,
    Identifier,
    LogDate,
    PlainText,
    ensure_plausible_calories,
)

from .models import MEAL_TYPES, SERVING_UNITS, FoodSource


class Nutrition(CamelModel):
    calories: int = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)


class NutritionInput(Nutrition):
    """Submitted nutrition: bounded, with calories consistent with the macros.

    Separate from ``Nutrition`` so the stricter input rules never make an
    already-stored food unreadable.
    """

    calories: int = Field(ge=0, le=MAX_CALORIES)
    protein: float = Field(ge=0, le=MAX_MACRO_G)
    carbs: float = Field(ge=0, le=MAX_MACRO_G)
    fat: float = Field(ge=0, le=MAX_MACRO_G)

    @model_validator(mode="after")
    def check_calories_match_macros(self) -> NutritionInput:
        ensure_plausible_calories(self.calories, self.protein, self.carbs, self.fat)
        return self


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
    name: PlainText = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    brand: PlainText | None = Field(default=None, max_length=MAX_NAME_LENGTH)
    serving_size: float = Field(gt=0, le=MAX_SERVING_SIZE)
    serving_unit: str
    serving_weight_g: float | None = Field(default=None, gt=0, le=MAX_SERVING_SIZE)
    nutrition: NutritionInput
    fibre_g: float | None = Field(default=None, ge=0, le=MAX_FIBRE_G)
    sugar_g: float | None = Field(default=None, ge=0, le=MAX_SUGAR_G)
    sodium_mg: float | None = Field(default=None, ge=0, le=MAX_SODIUM_MG)

    @field_validator("serving_unit")
    @classmethod
    def check_serving_unit(cls, value: str) -> str:
        return validate_choice(value, SERVING_UNITS, "servingUnit")


QuantityUnit = Literal["serving", "g"]

# Upper bound for a logged amount, in servings or grams.
_MAX_QUANTITY = MAX_SERVING_SIZE

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

    date: LogDate
    meal: str
    food_id: Identifier | None = None
    quantity: float | None = Field(default=None, gt=0, le=_MAX_QUANTITY)
    quantity_unit: QuantityUnit = "serving"
    name: PlainText | None = Field(default=None, min_length=1, max_length=MAX_NAME_LENGTH)
    amount_label: PlainText | None = Field(default=None, min_length=1, max_length=MAX_LABEL_LENGTH)
    source: FoodSource | None = None
    calories: int | None = Field(default=None, ge=0, le=MAX_CALORIES)
    protein: float | None = Field(default=None, ge=0, le=MAX_MACRO_G)
    carbs: float | None = Field(default=None, ge=0, le=MAX_MACRO_G)
    fat: float | None = Field(default=None, ge=0, le=MAX_MACRO_G)

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
            ensure_plausible_calories(
                cast(int, self.calories),
                cast(float, self.protein),
                cast(float, self.carbs),
                cast(float, self.fat),
            )
        return self


class UpdateFoodEntryInput(CamelModel):
    """Fields to change; anything omitted is left as it is.

    ``date`` and ``meal`` apply to every entry. A saved food's entry changes
    its ``quantity``/``quantity_unit`` (nutrition is re-scaled from the food);
    a quick add changes its values directly.
    """

    date: LogDate | None = None
    meal: str | None = None
    quantity: float | None = Field(default=None, gt=0, le=_MAX_QUANTITY)
    quantity_unit: QuantityUnit | None = None
    name: PlainText | None = Field(default=None, min_length=1, max_length=MAX_NAME_LENGTH)
    amount_label: PlainText | None = Field(default=None, min_length=1, max_length=MAX_LABEL_LENGTH)
    calories: int | None = Field(default=None, ge=0, le=MAX_CALORIES)
    protein: float | None = Field(default=None, ge=0, le=MAX_MACRO_G)
    carbs: float | None = Field(default=None, ge=0, le=MAX_MACRO_G)
    fat: float | None = Field(default=None, ge=0, le=MAX_MACRO_G)

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
