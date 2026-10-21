"""Profile and nutrition-target API contracts."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field, field_validator, model_validator

from app.analytics.energy import ActivityLevel, Sex
from app.shared.schema import CamelModel, validate_choice
from app.shared.timezones import is_known_timezone
from app.shared.validation import (
    MAX_ABS_WEEKLY_RATE_KG,
    MAX_BODY_WEIGHT_KG,
    MAX_HEIGHT_CM,
    MAX_NAME_LENGTH,
    MAX_TARGET_CALORIES,
    MAX_TARGET_CARBS_G,
    MAX_TARGET_FAT_G,
    MAX_TARGET_PROTEIN_G,
    MIN_BODY_WEIGHT_KG,
    MIN_HEIGHT_CM,
    MIN_TARGET_CALORIES,
    BirthDate,
    PlainText,
    ensure_plausible_calories,
    ensure_unique,
)
from app.workout.models import EQUIPMENT

from .models import ExperienceLevel, Goal, TargetSource


class DailyTargets(CamelModel):
    calories: int = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)


class TargetVersionRead(DailyTargets):
    """One version of the targets: what they were set to, from which day, and by what."""

    version: int
    effective_date: date
    source: TargetSource
    changed_at: datetime


class UpdateTargetsInput(DailyTargets):
    """Targets as submitted: bounded, and calories consistent with the macros.

    Separate from ``DailyTargets`` so the stricter input rules never make an
    already-stored target unreadable.
    """

    calories: int = Field(ge=MIN_TARGET_CALORIES, le=MAX_TARGET_CALORIES)
    protein: float = Field(ge=0, le=MAX_TARGET_PROTEIN_G)
    carbs: float = Field(ge=0, le=MAX_TARGET_CARBS_G)
    fat: float = Field(ge=0, le=MAX_TARGET_FAT_G)

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
    timezone: str
    # False until the sign-up guide is finished (POST /profile/onboarding).
    onboarded: bool
    # Empty only before the sign-up guide.
    date_of_birth: date | None
    sex: Sex | None
    activity_level: ActivityLevel | None


class TimezoneInput(CamelModel):
    timezone: str = Field(min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def check_known(cls, value: str) -> str:
        if not is_known_timezone(value):
            raise ValueError("must be an IANA timezone name such as Asia/Singapore")
        return value


class UpdateProfileInput(CamelModel):
    name: PlainText = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    height_cm: float = Field(ge=MIN_HEIGHT_CM, le=MAX_HEIGHT_CM)
    goal: Goal
    # No health limit by design (the app cautions instead); only the column's capacity.
    weekly_rate_kg: float = Field(ge=-MAX_ABS_WEEKLY_RATE_KG, le=MAX_ABS_WEEKLY_RATE_KG)
    # As the Profile form and the sign-up guide allow: the coach plans training around it.
    training_days_per_week: int = Field(ge=1, le=7)
    experience_level: ExperienceLevel
    date_of_birth: BirthDate
    sex: Sex
    activity_level: ActivityLevel
    equipment: list[str] = Field(default_factory=list, max_length=len(EQUIPMENT))

    @field_validator("equipment")
    @classmethod
    def check_equipment(cls, value: list[str]) -> list[str]:
        return ensure_unique([validate_choice(item, EQUIPMENT, "equipment") for item in value], "equipment")


class EstimateTargetsInput(CamelModel):
    """What the estimate needs, as entered in the sign-up guide before anything is saved."""

    height_cm: float = Field(ge=MIN_HEIGHT_CM, le=MAX_HEIGHT_CM)
    weight_kg: float = Field(ge=MIN_BODY_WEIGHT_KG, le=MAX_BODY_WEIGHT_KG)
    date_of_birth: BirthDate
    sex: Sex
    activity_level: ActivityLevel
    goal: Goal
    weekly_rate_kg: float = Field(ge=-MAX_ABS_WEEKLY_RATE_KG, le=MAX_ABS_WEEKLY_RATE_KG)


class TargetEstimateRead(DailyTargets):
    """Estimated targets, with the steps that led to them (kcal/day)."""

    resting: int
    maintenance: int
    # For the weekly goal: negative when losing.
    adjustment: int


class OnboardingInput(UpdateProfileInput):
    """The sign-up guide: the profile, today's weight, and the starting daily targets."""

    weight_kg: float = Field(ge=MIN_BODY_WEIGHT_KG, le=MAX_BODY_WEIGHT_KG)
    targets: UpdateTargetsInput
