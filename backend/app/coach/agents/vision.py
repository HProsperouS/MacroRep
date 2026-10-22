"""Estimating a meal from a photo, a tool of the nutrition side (plan.md §9.7).

The model names each food it sees and estimates the portion and its nutrition. The result
is only an estimate for the user to correct and confirm; nothing is logged here, and the
photo is never stored: it is sent to the model and dropped.
"""

from __future__ import annotations

import logging

from app.analytics.nutrition import calories_implausibly_low, macro_calories

from .ask import ask_with_retry, logged_run, output_limits
from .metrics import RunMetrics
from .model import CoachModel
from .schemas import PhotoEstimate, PhotoItem

logger = logging.getLogger(__name__)

# A transient model error is tried once more, if there's still time; the user can always
# take another photo.
PHOTO_ATTEMPTS = 2
# The user is waiting, and the browser gives up at 45 s (frontend/src/api/food-api.ts).
PHOTO_TIMEOUT_SECONDS = 35

PHOTO_INSTRUCTIONS = f"""You estimate the nutrition of a meal from a photo, for a food log.
List each distinct food or drink you can see, with a short everyday name, how the portion
looks, its weight in grams, and its calories, protein, carbs and fat for that portion.
Judge the portion from what's visible (plate and bowl size, cutlery, hands) and use typical
recipes and nutrition tables. Count cooking oil, sauces and dressings you can see or that
the dish normally has, and say in note what you couldn't judge, such as hidden oil or how
deep a bowl is. If there's no food or drink in the photo, return no items and say so in
note. The user will check and correct every value before anything is logged.
{output_limits(PhotoEstimate)}"""


def _consistent(item: PhotoItem) -> PhotoItem:
    """Calories no lower than the macros allow, since the log refuses an entry far below them,
    and still within the schema's limit."""

    if calories_implausibly_low(item.calories, item.protein, item.carbs, item.fat):
        implied = round(macro_calories(item.protein, item.carbs, item.fat))
        return item.model_copy(update={"calories": min(implied, _MAX_ITEM_CALORIES)})
    return item


_MAX_ITEM_CALORIES = 5_000  # PhotoItem.calories


async def estimate_photo(model: CoachModel, image: str, user_id: str) -> PhotoEstimate | None:
    """The estimate for ``image`` (a data: URL), or None when the model couldn't give one.
    Logged as ``food photo estimated`` with the item count and run metrics, never the image."""

    metrics = RunMetrics(model=model.name)

    async def estimate() -> PhotoEstimate | None:
        found = await ask_with_retry(
            model,
            "food_photo",
            PHOTO_INSTRUCTIONS,
            {},
            PhotoEstimate,
            metrics,
            attempts=PHOTO_ATTEMPTS,
            # A retry that would start past half the budget wouldn't finish in time.
            retry_within_seconds=PHOTO_TIMEOUT_SECONDS / 2,
            images=(image,),
        )
        return (
            found.model_copy(update={"items": [_consistent(item) for item in found.items]}) if found else None
        )

    return await logged_run(
        estimate(),
        metrics=metrics,
        timeout_seconds=PHOTO_TIMEOUT_SECONDS,
        log=logger,
        event="food photo estimated",
        failure_event="food photo estimate failed",
        extra={"user_id": user_id},
        details=lambda found: {"items": len(found.items) if found else None},
    )
