"""Revising a proposal at the user's request in Coach Chat ("request changes", plan.md §9.2).

The Nutrition or Workout agent is asked again with the user's request, and its answer goes
through the same path as a weekly check-in: the limits in ``validate.py``, the rule that a
calorie cut can't come with heavier training, and the Reviewer. What comes out is a pending
proposal the user applies on its card, never a change by itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ..pipeline import ProposalDraft
from .ask import ask_agent
from .drafts import nutrition_draft, training_draft
from .graph import (
    NUTRITION_INSTRUCTIONS,
    REVIEWER_INSTRUCTIONS,
    WORKOUT_INSTRUCTIONS,
    nutrition_context,
    reviewer_context,
    workout_context,
)
from .metrics import RunMetrics
from .model import CoachModel
from .schemas import NutritionAdvice, Review, WorkoutAdvice
from .validate import resolve_conflicts, validate_nutrition, validate_workout

ProposalKindName = Literal["nutrition", "training"]

REVISION_NOTE = """
The user has asked for a change to this week's proposal: user_request, in their words as
restated by the coach. current_proposal is what was proposed before, if anything. The
request comes first: when it fits within the limits above, follow it exactly, even where the
figures alone would suggest a different change, and put any concern in uncertainty. Only a
request that would break a limit is brought as close as the limit allows. Change nothing the
request doesn't ask about: for training, return every adjustment the proposal should now
have, keeping current_proposal's others as they were. If the request is to keep things as
they are, answer with action "keep"."""


@dataclass(frozen=True)
class Revision:
    """A revised proposal to store, or None with the reason to tell the user. ``withdraw``
    means the agent now proposes no change at all, so a pending proposal should go."""

    draft: ProposalDraft | None
    message: str
    withdraw: bool = False


def _increases_load(changes: Sequence[Mapping[str, Any]]) -> bool:
    return any(float(change["after"]) > float(change["before"]) for change in changes)


def _calorie_target(changes: Sequence[Mapping[str, Any]]) -> int | None:
    return next((int(float(c["after"])) for c in changes if c.get("id") == "calories"), None)


async def revise(
    model: CoachModel,
    metrics: RunMetrics,
    kind: ProposalKindName,
    snapshot: Mapping[str, Any],
    request: str,
    current: Mapping[str, Any] | None,
    other_changes: Sequence[Mapping[str, Any]] | None,
) -> Revision:
    """``current`` is the proposal of this kind being replaced, if any (for the agent to see);
    ``other_changes`` the changes of the other kind's pending or applied proposal, if any."""

    current_target = int(snapshot["target_calories"])
    revision_context = {"user_request": request, "current_proposal": current}
    if kind == "nutrition":
        nutrition = await ask_agent(
            model,
            "nutrition",
            NUTRITION_INSTRUCTIONS + REVISION_NOTE,
            {**nutrition_context(snapshot), **revision_context},
            NutritionAdvice,
            metrics,
        )
        if nutrition is None:
            return Revision(None, "I couldn't work out a revised calorie target. Please try again.")
        new_target, notes = validate_nutrition(nutrition, current_target)
        if new_target is None:
            return Revision(
                None, f"I'd keep the calorie target as it is: {nutrition.headline}", withdraw=True
            )
        if new_target < current_target and other_changes and _increases_load(other_changes):
            return Revision(
                None,
                "A lower calorie target can't go with the training change that adds load: eating "
                "less while training harder undercuts recovery. Reject that training change first, "
                "then ask again.",
            )
        review = await _review(model, metrics, snapshot, request, nutrition=nutrition.model_dump())
        if review is not None and not review.keep_nutrition:
            return Revision(None, f"The reviewer held this change back: {review.note}")
        note = _note(review, notes)
        return _revised(nutrition_draft(nutrition, current_target, new_target, note))

    workout = await ask_agent(
        model,
        "workout",
        WORKOUT_INSTRUCTIONS + REVISION_NOTE,
        {**workout_context(snapshot), **revision_context},
        WorkoutAdvice,
        metrics,
    )
    if workout is None:
        return Revision(None, "I couldn't work out a revised training change. Please try again.")
    adjustments, notes = validate_workout(workout, snapshot.get("routines") or [])
    if not adjustments:
        return Revision(None, f"I'd leave training as it is: {workout.headline}", withdraw=True)
    cut_to = _calorie_target(other_changes or [])
    adjustments, conflict_notes = resolve_conflicts(cut_to, current_target, adjustments)
    if not adjustments:
        return Revision(None, f"I'd leave training as it is: {' '.join(conflict_notes)}")
    review = await _review(model, metrics, snapshot, request, workout=workout.model_dump())
    if review is not None and not review.keep_workout:
        return Revision(None, f"The reviewer held this change back: {review.note}")
    return _revised(training_draft(workout, adjustments, _note(review, [*notes, *conflict_notes])))


async def _review(
    model: CoachModel,
    metrics: RunMetrics,
    snapshot: Mapping[str, Any],
    request: str,
    nutrition: Mapping[str, Any] | None = None,
    workout: Mapping[str, Any] | None = None,
) -> Review | None:
    context = {**reviewer_context(snapshot, nutrition, workout), "user_request": request}
    return await ask_agent(model, "reviewer", REVIEWER_INSTRUCTIONS, context, Review, metrics)


def _note(review: Review | None, notes: Sequence[str]) -> str:
    first = (
        review.note
        if review
        else "The reviewer couldn't check this revision; validation rules still applied."
    )
    return " ".join(["Revised at your request.", first, *notes])


def _revised(draft: ProposalDraft) -> Revision:
    return Revision(draft, f"I've revised the proposal: {draft.headline}. Review it on its card to apply it.")
