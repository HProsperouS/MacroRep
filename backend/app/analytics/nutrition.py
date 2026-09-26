"""Portion scaling, intake averages, logging adherence, and estimated energy expenditure."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

# Approximate energy content of one kilogram of body-mass change. A widely
# used rule of thumb (roughly 3500 kcal/lb); real tissue composition varies.
KCAL_PER_KG_BODY_MASS = 7700


class Nutrients(NamedTuple):
    calories: int
    protein: float
    carbs: float
    fat: float


def _round_half_up(value: float, places: int) -> Decimal:
    # Python's round() rounds halves to even; the frontend's preview uses
    # Math.round (halves up), and the two must agree on the logged value.
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def scale_nutrients(per_serving: Nutrients, servings: float) -> Nutrients:
    """Nutrition for ``servings`` servings: calories to whole kcal, macros to 0.1 g."""

    return Nutrients(
        calories=int(_round_half_up(per_serving.calories * servings, 0)),
        protein=float(_round_half_up(per_serving.protein * servings, 1)),
        carbs=float(_round_half_up(per_serving.carbs * servings, 1)),
        fat=float(_round_half_up(per_serving.fat * servings, 1)),
    )


KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_CARBS = 4
KCAL_PER_G_FAT = 9

# Below this share of the macro-implied energy, entered calories can't be real.
MIN_CALORIE_SHARE_OF_MACROS = 0.5
# Macro totals under this are too small for the comparison to mean anything.
MIN_MACRO_KCAL_TO_CHECK = 50


def macro_calories(protein: float, carbs: float, fat: float) -> float:
    """Energy implied by the macros (Atwater factors 4 / 4 / 9 kcal per gram)."""

    return protein * KCAL_PER_G_PROTEIN + carbs * KCAL_PER_G_CARBS + fat * KCAL_PER_G_FAT


def calories_implausibly_low(calories: float, protein: float, carbs: float, fat: float) -> bool:
    """True when entered calories are under half of what the macros imply.

    Only this direction is checked. Calories *above* the macros are normal:
    alcohol (~7 kcal/g) carries energy without protein, carbs, or fat, and a
    quick add often has calories with no macros at all. Calories modestly
    *below* are normal too: fibre counts as carbohydrate but yields about half
    the energy, and labels round. Under half, though, the numbers can't both
    be right, e.g. 900 g of protein (3,600 kcal) logged as 10 kcal.
    """

    implied = macro_calories(protein, carbs, fat)
    return implied >= MIN_MACRO_KCAL_TO_CHECK and calories < implied * MIN_CALORIE_SHARE_OF_MACROS


def average_daily_calories(calories_by_date: Mapping[date, float]) -> float | None:
    """Mean intake over the days that have any food logged.

    Days with nothing logged are excluded rather than counted as zero intake:
    an unlogged day means "unknown", not "ate nothing". None when no day is logged.
    """

    if not calories_by_date:
        return None
    return sum(calories_by_date.values()) / len(calories_by_date)


def logging_adherence_percent(logged_days: int, total_days: int) -> float:
    """Share of days in a period with food logged, as a percentage clamped to 0-100."""

    if total_days <= 0:
        return 0.0
    return round(min(max(logged_days / total_days, 0.0), 1.0) * 100, 1)


def estimate_expenditure(avg_intake_kcal: float, trend_change_kg: float, days: int) -> float:
    """Estimated daily energy expenditure (kcal/day) from intake and the weight trend.

    Energy balance: whatever was eaten and not reflected as weight change was
    expended. Losing weight means expenditure exceeded intake, and vice versa.
    """

    if days <= 0:
        return round(avg_intake_kcal)
    return round(avg_intake_kcal - (trend_change_kg * KCAL_PER_KG_BODY_MASS) / days)
