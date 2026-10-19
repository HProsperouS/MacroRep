"""Product-defined bounds every proposal is held to, whatever an agent suggests.

Deliberately conservative (plan.md §18): an adjustment beyond a bound is clamped
to it, with a note saying so, rather than passed on.
"""

from __future__ import annotations

MIN_TARGET_CALORIES = 1_000
MAX_TARGET_CALORIES = 6_000
# Largest change to the daily calorie target one check-in may propose.
MAX_WEEKLY_CALORIE_CHANGE = 300
CALORIE_STEP = 50

MIN_WORKING_SETS = 1
MAX_WORKING_SETS = 10
MAX_SET_CHANGE = 1
# Largest change to a target weight, as a share of the current one.
MAX_LOAD_CHANGE_SHARE = 0.10
LOAD_STEP_KG = 2.5
MIN_TARGET_REPS = 1
MAX_TARGET_REPS = 30
MAX_REP_CHANGE = 3

MAX_WORKOUT_ADJUSTMENTS = 6
