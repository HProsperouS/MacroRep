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
import time
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any, TypedDict, TypeVar, get_args, get_origin

from annotated_types import MaxLen
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from pydantic import BaseModel, ValidationError

from ..pipeline import CheckInDraft, ProposalChangeDraft, ProposalDraft, summarize_week
from . import limits
from .metrics import RunMetrics
from .model import AgentName, AgentTask, CoachModel, ModelUnavailableError
from .schemas import NutritionAdvice, Review, WorkoutAdvice
from .validate import ValidAdjustment, find_exercise, resolve_conflicts, validate_nutrition, validate_workout

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# One more try after an answer that doesn't parse; past that, retrying rarely helps.
STRUCTURED_OUTPUT_ATTEMPTS = 2
MODEL_RETRY = RetryPolicy(max_attempts=3, initial_interval=1.0, retry_on=ModelUnavailableError)
# Per-node ceiling on one model step, retries included.
NODE_TIMEOUT_SECONDS = 60


def _length_limits(schema: type[BaseModel], owner: str = "") -> list[str]:
    """The schema's length limits, in words: the model isn't held to them while generating."""

    found: list[str] = []
    for name, field in schema.model_fields.items():
        label = f"{owner}{name}"
        limit = next((m.max_length for m in field.metadata if isinstance(m, MaxLen)), None)
        if get_origin(field.annotation) is list:
            if limit is not None:
                found.append(f"at most {limit} {label} items")
            [item] = get_args(field.annotation)
            if isinstance(item, type) and issubclass(item, BaseModel):
                found += _length_limits(item, f"each {name} item's ")
        elif limit is not None:
            found.append(f"{label} under {limit} characters")
    return found


def output_limits(schema: type[BaseModel]) -> str:
    return f"Stay within these limits: {'; '.join(_length_limits(schema))}."


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
missed sessions, not the load, are what to fix. Cite the trends you used as evidence. No
injury advice.
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


async def ask_agent(
    model: CoachModel,
    agent: AgentName,
    instructions: str,
    context: Mapping[str, Any],
    output: type[T],
    metrics: RunMetrics,
    images: tuple[str, ...] = (),
) -> T | None:
    """The agent's validated answer, or None if it never produced one that fits the schema.
    Every model call is added to ``metrics``, including one that fails."""

    task = AgentTask(agent=agent, instructions=instructions, context=context, output=output, images=images)
    for attempt in range(1, STRUCTURED_OUTPUT_ATTEMPTS + 1):
        started = time.monotonic()
        try:
            reply = await model.generate(task)
        except BaseException as error:  # also a cancelled call, when the step runs out of time
            metrics.add(agent, started, "error", error=type(error).__name__)
            raise
        raw = reply.output
        try:
            parsed = output.model_validate_json(raw) if isinstance(raw, str) else output.model_validate(raw)
        except ValidationError:
            parsed = None
            logger.warning("agent output rejected", extra={"agent": agent, "attempt": attempt})
        metrics.add(
            agent,
            started,
            "invalid" if parsed is None else "valid",
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
        )
        if parsed is not None:
            return parsed
    return None


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
        "equipment": snapshot.get("equipment") or [],
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
        evidence=advice.evidence + ([advice.uncertainty] if advice.uncertainty else []),
        reviewer_note=note,
    )


def training_draft(advice: WorkoutAdvice, adjustments: list[ValidAdjustment], note: str) -> ProposalDraft:
    return ProposalDraft(
        id="training",
        kind="training",
        headline=advice.headline,
        changes=[_training_change(index, adjustment) for index, adjustment in enumerate(adjustments)],
        evidence=advice.evidence + ([advice.uncertainty] if advice.uncertainty else []),
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


def _finalize(state: CoachState) -> dict[str, Any]:
    snapshot = state["snapshot"]
    current_target = int(snapshot["target_calories"])
    nutrition = NutritionAdvice.model_validate(state["nutrition"]) if state.get("nutrition") else None
    workout = WorkoutAdvice.model_validate(state["workout"]) if state.get("workout") else None
    review = Review.model_validate(state["review"]) if state.get("review") else None

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

    summary, stats = summarize_week(snapshot)
    conflicts = sum(1 for finding in review.findings if finding.severity == "conflict") if review else 0
    pipeline = [
        {
            "id": "gather",
            "title": "Gather week's data",
            "detail": "Food log, workouts, weigh-ins.",
            "status": "done",
        },
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
            "detail": "Apply, edit or reject below." if proposals else "Nothing to change this week.",
            "status": "waiting" if proposals else "done",
        },
    ]
    draft = CheckInDraft(
        summary=summary,
        stats=stats,
        pipeline=pipeline,
        suggested_questions=[
            "Why did you suggest this change?",
            "What if I keep training the same but eat less?",
        ],
        proposals=proposals,
    )
    return _draft_to_dict(draft)


def _agent_step(step_id: str, title: str, headline: str | None) -> dict[str, str]:
    if headline is None:
        return {
            "id": step_id,
            "title": title,
            "detail": "Couldn't produce a valid proposal.",
            "status": "failed",
        }
    return {"id": step_id, "title": title, "detail": headline, "status": "done"}


def _draft_to_dict(draft: CheckInDraft) -> dict[str, Any]:
    return asdict(draft)


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
