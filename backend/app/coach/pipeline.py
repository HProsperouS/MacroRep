"""Placeholder check-in generation.

MacroRep's product vision is a multi-agent AI coach that reviews a user's
week and proposes nutrition/training adjustments. Building that pipeline
(agent roles, evidence gathering, LLM-backed proposal drafting) is a separate
piece of work; this module is the seam it plugs into. `draft_check_in` below
is a deterministic, rule-based stand-in with the same output shape
(`CheckInDraft`) so the rest of the app — persistence, API, frontend — can be
built and tested against a stable contract today, and the real pipeline can
replace this function's body later without touching any caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProposalChangeDraft:
    id: str
    label: str
    unit: str
    before: float
    after: float
    step: float


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


_CALORIE_ADJUST_STEP = 50
_ADHERENCE_HIGH = 80


def draft_check_in(
    *,
    week_label: str,
    avg_calories: float,
    target_calories: int,
    adherence_percent: float,
    workouts_done: int,
    workouts_planned: int,
    weight_change_kg: float,
    goal_rate_kg_per_week: float,
) -> CheckInDraft:
    """Rule-based week review: compare intake/adherence/training against targets.

    Deliberately simple (linear thresholds, no learning) — it exists to make
    the check-in pipeline observable end-to-end, not to be a good coach.
    """

    pipeline = [
        {
            "id": "gather",
            "title": "Gather week's data",
            "detail": "Food log, workouts, weigh-ins.",
            "status": "done",
        },
        {
            "id": "analyze",
            "title": "Analyze adherence & trend",
            "detail": f"{adherence_percent:.0f}% logging adherence.",
            "status": "done",
        },
        {
            "id": "propose",
            "title": "Draft proposals",
            "detail": "Rule-based placeholder pipeline.",
            "status": "done",
        },
    ]

    calorie_gap = avg_calories - target_calories
    on_track = abs(weight_change_kg - goal_rate_kg_per_week) < 0.15

    summary = (
        f"Averaged {avg_calories:.0f} kcal/day against a {target_calories} kcal target, "
        f"with {adherence_percent:.0f}% of days logged and {workouts_done}/{workouts_planned} "
        "planned workouts completed."
    )

    stats = [
        {"label": "Avg calories", "value": f"{avg_calories:.0f} kcal"},
        {"label": "Adherence", "value": f"{adherence_percent:.0f}%"},
        {"label": "Workouts", "value": f"{workouts_done}/{workouts_planned}"},
        {"label": "Weight change", "value": f"{weight_change_kg:+.2f} kg"},
    ]

    proposals: list[ProposalDraft] = []
    if adherence_percent >= _ADHERENCE_HIGH and not on_track:
        new_target = round(target_calories - calorie_gap + (goal_rate_kg_per_week - weight_change_kg) * 1100)
        proposals.append(
            ProposalDraft(
                id="nutrition-calories",
                kind="nutrition",
                headline=f"Adjust daily target to {new_target} kcal",
                changes=[
                    ProposalChangeDraft(
                        id="calories",
                        label="Daily calories",
                        unit="kcal",
                        before=target_calories,
                        after=new_target,
                        step=_CALORIE_ADJUST_STEP,
                    )
                ],
                evidence=[
                    f"Trend weight changed {weight_change_kg:+.2f} kg vs "
                    f"a {goal_rate_kg_per_week:+.2f} kg/week goal.",
                    f"Logging adherence was {adherence_percent:.0f}%, high enough to trust the intake data.",
                ],
                reviewer_note="Placeholder rule-based proposal — replace with the multi-agent pipeline.",
            )
        )

    suggested_questions = [
        "Why did you suggest this change?",
        "What if I keep training the same but eat less?",
    ]

    return CheckInDraft(
        summary=summary,
        stats=stats,
        pipeline=pipeline,
        suggested_questions=suggested_questions,
        proposals=proposals,
    )
