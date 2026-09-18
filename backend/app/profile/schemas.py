"""Profile and nutrition-target API contracts."""

from __future__ import annotations

from pydantic import Field

from app.shared.schema import CamelModel

from .models import Goal


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


class UpdateProfileInput(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    height_cm: float = Field(gt=0, le=300)
    goal: Goal
    weekly_rate_kg: float
    training_days_per_week: int = Field(ge=0, le=7)
