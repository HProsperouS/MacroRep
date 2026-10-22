"""Turning validated agent advice into the proposals the user decides on."""

from __future__ import annotations

from ..pipeline import ProposalChangeDraft, ProposalDraft
from . import limits
from .schemas import NutritionAdvice, WorkoutAdvice
from .validate import ValidAdjustment


def _evidence(advice: NutritionAdvice | WorkoutAdvice) -> list[str]:
    """What the agent based its advice on, and what it was unsure of, if anything."""

    return advice.evidence + ([advice.uncertainty] if advice.uncertainty else [])


def nutrition_draft(
    advice: NutritionAdvice, current_target: int, new_target: int, note: str
) -> ProposalDraft:
    return ProposalDraft(
        id="nutrition",
        kind="nutrition",
        headline=f"Adjust your daily target to {new_target:,} kcal",
        changes=[
            ProposalChangeDraft(
                id="calories",
                label="Daily calories",
                unit="kcal",
                before=current_target,
                after=new_target,
                step=limits.CALORIE_STEP,
            )
        ],
        evidence=_evidence(advice),
        reviewer_note=note,
    )


def training_draft(advice: WorkoutAdvice, adjustments: list[ValidAdjustment], note: str) -> ProposalDraft:
    return ProposalDraft(
        id="training",
        kind="training",
        headline=advice.headline,
        changes=[_training_change(index, adjustment) for index, adjustment in enumerate(adjustments)],
        evidence=_evidence(advice),
        reviewer_note=note,
    )


_FIELD_LABELS = {
    "working_sets": ("working sets", "sets", 1.0),
    "target_weight_kg": ("target weight", "kg", limits.LOAD_STEP_KG),
    "target_reps": ("target reps", "reps", 1.0),
}


def _training_change(index: int, adjustment: ValidAdjustment) -> ProposalChangeDraft:
    label, unit, step = _FIELD_LABELS[adjustment.field]
    return ProposalChangeDraft(
        id=f"training-{index + 1}",
        label=f"{adjustment.exercise_name} · {label}",
        unit=unit,
        before=adjustment.before,
        after=adjustment.after,
        step=step,
        routine_id=adjustment.routine_id,
        exercise_id=adjustment.exercise_id,
        field=adjustment.field,
    )
