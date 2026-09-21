"""Profile and nutrition-target API contracts."""

from __future__ import annotations

from pydantic import Field, field_validator

from app.shared.schema import CamelModel, validate_choice
from app.workout.models import EQUIPMENT

from .models import ExperienceLevel, Goal


class DailyTargets(CamelModel):
    calories: int = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)


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
    name: str = Field(min_length=1, max_length=255)
    height_cm: float = Field(gt=0, le=300)
    goal: Goal
    weekly_rate_kg: float
    training_days_per_week: int = Field(ge=0, le=7)
    experience_level: ExperienceLevel
    equipment: list[str] = Field(default_factory=list)

    @field_validator("equipment")
    @classmethod
    def check_equipment(cls, value: list[str]) -> list[str]:
        return [validate_choice(item, EQUIPMENT, "equipment") for item in value]
