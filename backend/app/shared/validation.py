"""Accepted ranges for user input, and the reusable types that enforce them.

The approach is an allow-list: every numeric field has a plausible range,
every text field a trimmed, bounded length with no hidden control characters,
and every id a fixed character set, rather than a list of known-bad values to
block. The ranges are sanity bounds (nobody logs a 5,000 kg
weigh-in), deliberately wide, and each fits the database column behind it so
an out-of-range value is a clean 422 rather than a database overflow (a 500).
Health rules, such as how far a coach may change a target, are separate
business rules and don't live here.

The frontend's forms mirror these ranges; keep the two in step.
"""

from __future__ import annotations

import unicodedata
from datetime import date, timedelta
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

from app.analytics.nutrition import calories_implausibly_low, macro_calories

# Text
MAX_NAME_LENGTH = 255
MAX_LABEL_LENGTH = 64
MAX_SEARCH_LENGTH = 100
MAX_CHAT_LENGTH = 2_000

# Dates. One day of future tolerance: a user ahead of UTC is already on
# "tomorrow" by the server's clock.
EARLIEST_LOG_DATE = date(2000, 1, 1)
FUTURE_TOLERANCE = timedelta(days=1)

# Body
MIN_BODY_WEIGHT_KG = 20
MAX_BODY_WEIGHT_KG = 400
MIN_HEIGHT_CM = 50
MAX_HEIGHT_CM = 272
# Not a health limit (the weekly rate has none): the most the profile column
# can store. Anything larger would overflow the database.
MAX_ABS_WEEKLY_RATE_KG = 99.99

# Nutrition: per food-log entry, per serving of a food, and per daily target.
MAX_CALORIES = 10_000
MAX_MACRO_G = 1_000
MAX_FIBRE_G = 500
MAX_SUGAR_G = 1_000
MAX_SODIUM_MG = 50_000
MAX_SERVING_SIZE = 5_000

# Training
MAX_SET_WEIGHT_KG = 1_000
MAX_REPS = 100
MAX_EXERCISES_PER_WORKOUT = 50
MAX_SETS_PER_EXERCISE = 50
# Tolerated difference between the client's clock and the server's when
# checking that a workout didn't happen in the future.
CLOCK_SKEW = timedelta(minutes=10)

# Coach: an edited proposal value can't go below zero (e.g. a negative calorie
# target); the ceiling is a generic sanity bound shared by kcal, g, and kg.
MAX_PROPOSAL_VALUE = 10_000

# Characters that change how text *displays* without being visible: explicit
# direction overrides and isolates. "Alex\u202Egnp.exe" renders as
# "Alexexe.png", which is how they're used to disguise text.
_BIDI_CONTROLS = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
_LINE_BREAKS = frozenset("\n\r\t")


def _reject_hidden_characters(value: str, *, allow_line_breaks: bool) -> str:
    """Reject control characters (category Cc) and text-direction overrides.

    Beyond being invisible, a NUL byte can't be stored in Postgres at all; it
    would fail the request with a 500. Letters of any script and emoji are
    fine, including the zero-width joiners inside emoji like 👨‍👩‍👧, which are a
    different category (Cf) and render as one symbol.
    """

    for char in value:
        if unicodedata.category(char) == "Cc" and not (allow_line_breaks and char in _LINE_BREAKS):
            raise ValueError("must not contain control characters")
        if char in _BIDI_CONTROLS:
            raise ValueError("must not contain text-direction override characters")
    return value


# Single-line text such as a name or label. Whitespace is trimmed before the
# length checks, so "   " is too short.
PlainText = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    AfterValidator(lambda value: _reject_hidden_characters(value, allow_line_breaks=False)),
]

# Free text that may span lines, such as a chat message.
MultilineText = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    AfterValidator(lambda value: _reject_hidden_characters(value, allow_line_breaks=True)),
]

# A record id sent in a request body: UUID hex (e.g. "3f2a…"), "USR-…", or a
# seeded slug such as "food-egg". Anything else can't match a row, so it's
# rejected up front instead of reaching a query.
Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]


def _check_log_date(value: date) -> date:
    if value < EARLIEST_LOG_DATE:
        raise ValueError(f"must be on or after {EARLIEST_LOG_DATE.isoformat()}")
    if value > date.today() + FUTURE_TOLERANCE:
        raise ValueError("can't be in the future")
    return value


# The day a weigh-in or meal is logged against.
LogDate = Annotated[date, AfterValidator(_check_log_date)]


def ensure_plausible_calories(calories: float, protein: float, carbs: float, fat: float) -> None:
    """Raise if calories are far below what the macros imply (see ``calories_implausibly_low``)."""

    if calories_implausibly_low(calories, protein, carbs, fat):
        implied = round(macro_calories(protein, carbs, fat))
        raise ValueError(
            f"Calories look too low for these macros: they add up to {implied:,} kcal. "
            "Check for a missing digit or a value in the wrong field."
        )


def ensure_unique(values: list[str], field_name: str) -> list[str]:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must not repeat a value")
    return values
