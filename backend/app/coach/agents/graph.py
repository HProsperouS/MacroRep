"""The weekly check-in as a LangGraph flow.

    START ─┬─> nutrition ─┐
           └─> workout ───┴─> reviewer ─> finalize ─> END

Nutrition and Workout run in parallel, each seeing only its own slice of the frozen
snapshot. The Reviewer sees both proposals together and may hold either back. Finalize
is deterministic: it applies ``validate`` and turns the result into a ``CheckInDraft``.
The user's approval happens afterwards, through the proposals API, not inside the graph.

A model answer that doesn't match the output schema is asked for again once, then
that agent is given up on (its proposal is simply absent). A transient model error is
retried by LangGraph's retry policy; if it keeps failing, the run fails and the
check-in is marked failed. Each step is checkpointed under the check-in's id.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from ..pipeline import CheckInDraft, ProposalChangeDraft, ProposalDraft, gather_step, summarize_week
from . import limits
from .ask import ask_agent, output_limits
from .drafts import nutrition_draft, training_draft
from .metrics import RunMetrics
from .model import CoachModel, ModelUnavailableError
from .schemas import NutritionAdvice, Review, WorkoutAdvice
from .validate import find_exercise, resolve_conflicts, validate_nutrition, validate_workout

logger = logging.getLogger(__name__)

MODEL_RETRY = RetryPolicy(max_attempts=3, initial_interval=1.0, retry_on=ModelUnavailableError)
# Per-node ceiling on one model step, retries included.
NODE_TIMEOUT_SECONDS = 60


NUTRITION_INSTRUCTIONS = f"""You are the Nutrition agent of a fitness app's weekly check-in.
From the week's figures, decide whether the user's daily calorie target should change.

The figures: weight_change_kg is how much the user's trend weight (a smoothed average that
already filters out day-to-day water swings) moved over these 7 days, so it is a reliable
weekly rate, not a single noisy weigh-in. goal_rate_kg_per_week is the planned rate:
negative to lose, positive to gain, 0 to maintain. food_log_days is how many of the 7 days
have food logged. avg_calories is the average over those days; target_gap_kcal is intake
minus target summed over the finished days logged (today isn't finished, so
complete_days + partial_days + missing_days is 6).

When food_log_days is at least 5 and the trend misses the goal rate by more than
about 0.2 kg a week, change the target to close the gap: lower it when weight is falling
slower than planned (or rising when it should fall), raise it when weight is falling faster
than planned (or not rising when it should). Roughly 1,100 kcal a day moves the rate by 1 kg a
week. If intake well above the target already explains the gap, keep the target and say so:
the target isn't the problem. Otherwise keep it.

Propose at most a {limits.MAX_WEEKLY_CALORIE_CHANGE} kcal change, never below
{limits.MIN_TARGET_CALORIES} kcal. Never treat an unlogged day as zero intake. If too few days
were logged to judge, keep the target and say why in `uncertainty`. Cite the figures you used
as evidence. You are not a medical service: no diagnoses, no extreme restriction.
{output_limits(NutritionAdvice)}"""

WORKOUT_INSTRUCTIONS = f"""You are the Workout agent of a fitness app's weekly check-in.
From completion, effort (RPE) and estimated-1RM trends, decide whether any exercise in the
user's scheduled routines should change its working sets, target weight or target reps.
In exercise_trends, recent_* is this week and prior_* the three weeks before; e1rm is the
estimated one-rep max from working sets. Only refer to routine and exercise ids you were
given. Small steps only: sets by {limits.MAX_SET_CHANGE}, weight by at most
{int(limits.MAX_LOAD_CHANGE_SHARE * 100)}%, reps by {limits.MAX_REP_CHANGE}. Rising RPE without
strength gains suggests easing off; low RPE with steady gains suggests progressing. When most planned
workouts were missed (completion_percent under about 70), don't increase anything: the
missed sessions, not the load, are what to fix. Pace progress to experience_level: a beginner
progressing smoothly can add weight or reps every week; an intermediate needs steadier
evidence over the weeks before progressing; an advanced lifter progresses rarely and by the
smallest step, and only on a clear trend. Cite the trends you used as evidence. No injury
advice.
{output_limits(WorkoutAdvice)}"""

REVIEWER_INSTRUCTIONS = f"""You are the Reviewer of a fitness app's weekly check-in.
You see the Nutrition and Workout proposals together. A lower calorie target together with
any increase in training load (working sets, target weight or target reps) is a conflict:
eating less while training harder undercuts recovery. Report it with severity "conflict" and
hold one of the two back. Also look for conclusions the data doesn't support and for anything
outside a fitness app's scope. You may hold a proposal back (keep_* = false), never add or
enlarge one. Write a short note the user will read.
{output_limits(Review)}"""


class CoachState(TypedDict, total=False):
    snapshot: dict[str, Any]
    nutrition: dict[str, Any] | None
    workout: dict[str, Any] | None
    review: dict[str, Any] | None
    draft: dict[str, Any]


def nutrition_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "target_calories",
        "avg_calories",
        "food_log_days",
        "adherence_percent",
        "complete_days",
        "partial_days",
        "missing_days",
        "target_gap_kcal",
        "weight_change_kg",
        "goal_rate_kg_per_week",
        "goal",
    )
    return {key: snapshot.get(key) for key in keys}


def workout_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("workouts_done", "workouts_planned", "completion_percent", "avg_rpe")
    return {
        **{key: snapshot.get(key) for key in keys},
        # Absent from snapshots taken before training data was gathered: then there's nothing to adjust.
        "routines": snapshot.get("routines") or [],
        "exercise_trends": snapshot.get("exercise_trends") or {},
        # Absent from snapshots taken before it was gathered: then pace as for an intermediate.
        "experience_level": snapshot.get("experience_level") or "intermediate",
    }


def _current_value(snapshot: Mapping[str, Any], routine_id: str, exercise_id: str, field: str) -> Any:
    found = find_exercise(snapshot.get("routines") or [], routine_id, exercise_id)
    return found[1].get(field) if found else None


def build_graph(model: CoachModel, metrics: RunMetrics) -> StateGraph[CoachState]:
    async def nutrition(state: CoachState) -> CoachState:
        advice = await ask_agent(
            model,
            "nutrition",
            NUTRITION_INSTRUCTIONS,
            nutrition_context(state["snapshot"]),
            NutritionAdvice,
            metrics,
        )
        return {"nutrition": advice.model_dump() if advice else None}

    async def workout(state: CoachState) -> CoachState:
        advice = await ask_agent(
            model, "workout", WORKOUT_INSTRUCTIONS, workout_context(state["snapshot"]), WorkoutAdvice, metrics
        )
        return {"workout": advice.model_dump() if advice else None}

    async def reviewer(state: CoachState) -> CoachState:
        context = reviewer_context(state["snapshot"], state.get("nutrition"), state.get("workout"))
        review = await ask_agent(model, "reviewer", REVIEWER_INSTRUCTIONS, context, Review, metrics)
        return {"review": review.model_dump() if review else None}

    def finalize(state: CoachState) -> CoachState:
        return {"draft": _finalize(state)}

    graph = StateGraph(CoachState)
    graph.add_node("nutrition", nutrition, retry_policy=MODEL_RETRY, timeout=NODE_TIMEOUT_SECONDS)
    graph.add_node("workout", workout, retry_policy=MODEL_RETRY, timeout=NODE_TIMEOUT_SECONDS)
    graph.add_node("reviewer", reviewer, retry_policy=MODEL_RETRY, timeout=NODE_TIMEOUT_SECONDS)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "nutrition")
    graph.add_edge(START, "workout")
    graph.add_edge(["nutrition", "workout"], "reviewer")
    graph.add_edge("reviewer", "finalize")
    graph.add_edge("finalize", END)
    return graph


def reviewer_context(
    snapshot: Mapping[str, Any], nutrition: Mapping[str, Any] | None, workout: Mapping[str, Any] | None
) -> dict[str, Any]:
    # The reviewer sees each training change next to the value it replaces.
    if workout is not None:
        workout = {
            **workout,
            "adjustments": [
                {
                    **adjustment,
                    "current_value": _current_value(
                        snapshot, adjustment["routine_id"], adjustment["exercise_id"], adjustment["field"]
                    ),
                }
                for adjustment in workout["adjustments"]
            ],
        }
    return {
        "current_calorie_target": snapshot["target_calories"],
        "missing_days": snapshot["missing_days"],
        "avg_rpe": snapshot["avg_rpe"],
        "weight_change_kg": snapshot["weight_change_kg"],
        "goal_rate_kg_per_week": snapshot["goal_rate_kg_per_week"],
        "nutrition": nutrition,
        "workout": workout,
    }


def _finalize(state: CoachState) -> dict[str, Any]:
    snapshot = state["snapshot"]
    nutrition = NutritionAdvice.model_validate(state["nutrition"]) if state.get("nutrition") else None
    workout = WorkoutAdvice.model_validate(state["workout"]) if state.get("workout") else None
    review = Review.model_validate(state["review"]) if state.get("review") else None
    proposals = _decide(snapshot, nutrition, workout, review)
    summary, stats = summarize_week(snapshot)
    draft = CheckInDraft(
        summary=summary,
        stats=stats,
        pipeline=_pipeline(nutrition, workout, review, bool(proposals)),
        suggested_questions=[
            "Why did you suggest this change?",
            "What if I keep training the same but eat less?",
        ],
        proposals=proposals,
    )
    return asdict(draft)


def _decide(
    snapshot: Mapping[str, Any],
    nutrition: NutritionAdvice | None,
    workout: WorkoutAdvice | None,
    review: Review | None,
) -> list[ProposalDraft]:
    """The proposals that survive validation, the reviewer and the conflict rule."""

    current_target = int(snapshot["target_calories"])
    new_target, nutrition_notes = validate_nutrition(nutrition, current_target)
    adjustments, workout_notes = validate_workout(workout, snapshot.get("routines") or [])
    # The reviewer is advisory: it can hold a proposal back, but validation still applies to
    # what's left. Its holds come first, so a cut it held back can't hold back training too.
    if review is not None and not review.keep_nutrition:
        new_target = None
    if review is not None and not review.keep_workout:
        adjustments = []
    adjustments, conflict_notes = resolve_conflicts(new_target, current_target, adjustments)

    review_note = (
        review.note
        if review
        else "The reviewer couldn't check these proposals; validation rules still applied."
    )
    proposals: list[ProposalDraft] = []
    if nutrition is not None and new_target is not None:
        note = " ".join([review_note, *nutrition_notes, *conflict_notes])
        proposals.append(nutrition_draft(nutrition, current_target, new_target, note))
    if workout is not None and adjustments:
        proposals.append(
            training_draft(workout, adjustments, " ".join([review_note, *workout_notes, *conflict_notes]))
        )
    return proposals


def _pipeline(
    nutrition: NutritionAdvice | None, workout: WorkoutAdvice | None, review: Review | None, proposed: bool
) -> list[dict[str, str]]:
    """The steps shown on the check-in, as they ended."""

    conflicts = sum(1 for finding in review.findings if finding.severity == "conflict") if review else 0
    return [
        gather_step(),
        _agent_step("nutrition", "Nutrition agent", nutrition.headline if nutrition else None),
        _agent_step("workout", "Workout agent", workout.headline if workout else None),
        {
            "id": "reviewer",
            "title": "Reviewer",
            "detail": (
                f"{conflicts} conflict{'s' if conflicts != 1 else ''} resolved."
                if conflicts
                else ("No conflicts found." if review else "Couldn't review; rules applied instead.")
            ),
            "status": "done" if review else "failed",
        },
        {
            "id": "decide",
            "title": "Your decision",
            "detail": "Apply, edit or reject below." if proposed else "Nothing to change this week.",
            "status": "waiting" if proposed else "done",
        },
    ]


def _agent_step(step_id: str, title: str, headline: str | None) -> dict[str, str]:
    if headline is None:
        return {
            "id": step_id,
            "title": title,
            "detail": "Couldn't produce a valid proposal.",
            "status": "failed",
        }
    return {"id": step_id, "title": title, "detail": headline, "status": "done"}


def draft_from_dict(data: Mapping[str, Any]) -> CheckInDraft:
    return CheckInDraft(
        summary=data["summary"],
        stats=list(data["stats"]),
        pipeline=list(data["pipeline"]),
        suggested_questions=list(data["suggested_questions"]),
        proposals=[
            ProposalDraft(
                **{key: value for key, value in proposal.items() if key != "changes"},
                changes=[ProposalChangeDraft(**change) for change in proposal["changes"]],
            )
            for proposal in data["proposals"]
        ],
    )


async def run_agents(
    snapshot: Mapping[str, Any],
    model: CoachModel,
    *,
    thread_id: str | None = None,
    checkpointer: BaseCheckpointSaver[str] | None = None,
    metrics: RunMetrics | None = None,
) -> CheckInDraft:
    """Run the check-in graph on ``snapshot``, adding each model call to ``metrics``. With a
    ``thread_id`` and ``checkpointer`` each step is saved, and a run that was interrupted
    continues from its last saved step."""

    metrics = metrics if metrics is not None else RunMetrics(model=model.name)
    start: CoachState = {"snapshot": dict(snapshot)}
    graph = build_graph(model, metrics).compile(checkpointer=checkpointer if thread_id else None)
    if thread_id is None or checkpointer is None:
        result = await graph.ainvoke(start)
        return draft_from_dict(result["draft"])
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    saved = await graph.aget_state(config)
    if "draft" in saved.values:
        metrics.resumed = True  # finished before an interruption: no model calls this time
        result = saved.values
    elif saved.next:
        metrics.resumed = True
        result = await graph.ainvoke(None, config)  # continue an interrupted run
    else:
        result = await graph.ainvoke(start, config)
    return draft_from_dict(result["draft"])
