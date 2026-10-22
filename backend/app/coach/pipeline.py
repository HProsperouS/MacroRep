"""The check-in's output contract, and the week's summary and headline stats.

``CheckInDraft`` is what generation produces and the service stores: the agents in
``agents/`` fill its proposals; the summary and stats come from the frozen snapshot,
deterministically, so they never depend on a model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


def gather_step() -> dict[str, str]:
    """The first step of every check-in, done before any agent runs. A new dict each time, as
    each check-in's pipeline is its own."""

    return {
        "id": "gather",
        "title": "Gather week's data",
        "detail": "Food log, workouts, weigh-ins.",
        "status": "done",
    }


# A week's total shortfall below this is within normal day-to-day noise.
_NOTABLE_WEEKLY_GAP_KCAL = 500


@dataclass
class ProposalChangeDraft:
    id: str
    label: str
    unit: str
    before: float
    after: float
    step: float
    # Set on a training change: which routine exercise and target it edits.
    routine_id: str | None = None
    exercise_id: str | None = None
    field: str | None = None


@dataclass
class ProposalDraft:
    id: str
    kind: str
    headline: str
    changes: list[ProposalChangeDraft]
    evidence: list[str]
    reviewer_note: str


@dataclass
class CheckInDraft:
    summary: str
    stats: list[dict[str, str]]
    pipeline: list[dict[str, str]]
    suggested_questions: list[str]
    proposals: list[ProposalDraft] = field(default_factory=list)


def summarize_week(snapshot: Mapping[str, Any]) -> tuple[str, list[dict[str, str]]]:
    """A plain-language summary of the week and its headline numbers."""

    avg_calories = float(snapshot["avg_calories"])
    target_calories = int(snapshot["target_calories"])
    adherence_percent = float(snapshot["adherence_percent"])
    partial_days = int(snapshot["partial_days"])
    target_gap = int(snapshot["target_gap_kcal"])
    workouts_done, workouts_planned = int(snapshot["workouts_done"]), int(snapshot["workouts_planned"])
    completion = snapshot["completion_percent"]
    avg_rpe = snapshot["avg_rpe"]
    weight_change = float(snapshot["weight_change_kg"])

    summary = (
        f"Averaged {avg_calories:.0f} kcal/day against a {target_calories} kcal target, "
        f"with {adherence_percent:.0f}% of days logged and {workouts_done}/{workouts_planned} "
        "planned workouts completed."
    )
    if target_gap <= -_NOTABLE_WEEKLY_GAP_KCAL:
        summary += f" Logged days came in {-target_gap:,} kcal under target in total."
        if partial_days:
            summary += (
                f" {partial_days} of them fell under half the target; if some food went unlogged,"
                " the real shortfall is smaller."
            )
    if avg_rpe is not None:
        summary += f" Average effort was RPE {float(avg_rpe):.1f}."

    workouts = f"{workouts_done}/{workouts_planned}"
    if completion is not None:
        workouts += f" ({float(completion):.0f}%)"
    stats = [
        {"label": "Avg calories", "value": f"{avg_calories:.0f} kcal"},
        {"label": "Vs target", "value": f"{target_gap:+,} kcal"},
        {"label": "Days logged", "value": f"{adherence_percent:.0f}%"},
        {"label": "Workouts", "value": workouts},
        {"label": "Avg RPE", "value": f"{float(avg_rpe):.1f}" if avg_rpe is not None else "—"},
        {"label": "Weight change", "value": f"{weight_change:+.2f} kg"},
    ]
    return summary, stats
