"""Profile and nutrition-target API contracts."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from app.shared.schema import CamelModel, validate_choice
from app.shared.validation import (
    MAX_ABS_WEEKLY_RATE_KG,
    MAX_CALORIES,
    MAX_HEIGHT_CM,
    MAX_MACRO_G,
    MAX_NAME_LENGTH,
    MIN_HEIGHT_CM,
    PlainText,
    ensure_plausible_calories,
    ensure_unique,
)
from app.workout.models import EQUIPMENT

from .models import ExperienceLevel, Goal


class DailyTargets(CamelModel):
    calories: int = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)


class UpdateTargetsInput(DailyTargets):
    """Targets as submitted: bounded, and calories consistent with the macros.

    Separate from ``DailyTargets`` so the stricter input rules never make an
    already-stored target unreadable.
    """

    calories: int = Field(ge=0, le=MAX_CALORIES)
    protein: float = Field(ge=0, le=MAX_MACRO_G)
    carbs: float = Field(ge=0, le=MAX_MACRO_G)
    fat: float = Field(ge=0, le=MAX_MACRO_G)

    @model_validator(mode="after")
    def check_calories_match_macros(self) -> UpdateTargetsInput:
        ensure_plausible_calories(self.calories, self.protein, self.carbs, self.fat)
        return self


class ProfileRead(CamelModel):
    name: str
    email: str
    height_cm: float
    goal: Goal
    weekly_rate_kg: float
    training_days_per_week: int
    experience_level: ExperienceLevel
    equipment: list[str]


class UpdateProfileInput(CamelModel):
    name: PlainText = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    height_cm: float = Field(ge=MIN_HEIGHT_CM, le=MAX_HEIGHT_CM)
    goal: Goal
    # No health limit by design (the app cautions instead); only the column's capacity.
    weekly_rate_kg: float = Field(ge=-MAX_ABS_WEEKLY_RATE_KG, le=MAX_ABS_WEEKLY_RATE_KG)
    training_days_per_week: int = Field(ge=0, le=7)
    experience_level: ExperienceLevel
    equipment: list[str] = Field(default_factory=list, max_length=len(EQUIPMENT))

    @field_validator("equipment")
    @classmethod
    def check_equipment(cls, value: list[str]) -> list[str]:
        return ensure_unique([validate_choice(item, EQUIPMENT, "equipment") for item in value], "equipment")
