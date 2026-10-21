"""Starting daily targets from a person's details: resting energy (Mifflin-St Jeor), times
an activity factor, adjusted for the weekly goal, then split into macros.

An estimate to start from, not a prescription: each weekly check-in then adjusts the
targets from what the user actually eats and weighs (see docs/analytics.md).
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import NamedTuple

from .nutrition import KCAL_PER_KG_BODY_MASS


class Sex(StrEnum):
    MALE = "male"
    FEMALE = "female"


class ActivityLevel(StrEnum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    VERY = "very"


# The usual multipliers for total daily energy from resting energy (Harris-Benedict's
# activity factors, as commonly paired with Mifflin-St Jeor).
ACTIVITY_FACTORS = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.VERY: 1.725,
}
# Mifflin-St Jeor's sex term.
_SEX_CONSTANT = {Sex.MALE: 5, Sex.FEMALE: -161}

# Protein per kg of body weight: higher while losing, to keep muscle.
PROTEIN_G_PER_KG = {"lose": 2.0, "maintain": 1.8, "gain": 1.8}
FAT_SHARE_OF_CALORIES = 0.25
CALORIE_STEP = 50


class TargetEstimate(NamedTuple):
    resting: int
    maintenance: int
    # Daily change for the weekly goal: negative when losing.
    adjustment: int
    calories: int
    protein: int
    carbs: int
    fat: int


def age_on(birth: date, today: date) -> int:
    """Whole years from ``birth`` to ``today``."""

    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def resting_energy(weight_kg: float, height_cm: float, age: int, sex: Sex) -> float:
    """Mifflin-St Jeor resting energy, kcal/day."""

    return 10 * weight_kg + 6.25 * height_cm - 5 * age + _SEX_CONSTANT[sex]


def estimate_targets(
    *,
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    activity: ActivityLevel,
    goal: str,
    weekly_rate_kg: float,
    min_calories: int,
    max_calories: int,
    max_protein_g: int,
    max_carbs_g: int,
) -> TargetEstimate:
    """Daily targets for the goal. Calories are rounded to 50 kcal within the allowed range;
    protein follows body weight, fat is a quarter of the calories, and carbs take the rest.
    """

    resting = resting_energy(weight_kg, height_cm, age, sex)
    maintenance = resting * ACTIVITY_FACTORS[activity]
    adjustment = 0.0 if goal == "maintain" else weekly_rate_kg * KCAL_PER_KG_BODY_MASS / 7
    calories = round((maintenance + adjustment) / CALORIE_STEP) * CALORIE_STEP
    calories = min(max(calories, min_calories), max_calories)

    fat = round(calories * FAT_SHARE_OF_CALORIES / 9)
    # Protein by body weight, but never more than the calories left after fat, so the
    # macros always add up to the calories (a heavy person on a low target).
    room_for_protein = (calories - fat * 9) // 4
    protein = min(round(weight_kg * PROTEIN_G_PER_KG[goal]), max_protein_g, room_for_protein)
    # Within the target limit too: at the top of the range, carbs could otherwise pass it.
    carbs = min(max(round((calories - protein * 4 - fat * 9) / 4), 0), max_carbs_g)
    return TargetEstimate(
        resting=round(resting),
        maintenance=round(maintenance),
        adjustment=round(adjustment),
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat,
    )
