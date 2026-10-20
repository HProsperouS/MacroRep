"""The check-in agents: what each sees, how their output is checked, and how the graph recovers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import RetryPolicy

from app.coach.agents import graph as graph_module
from app.coach.agents.graph import nutrition_context, run_agents, workout_context
from app.coach.agents.metrics import RunMetrics
from app.coach.agents.model import AgentTask, FakeCoachModel, ModelReply, ModelUnavailableError, _fake_review
from app.coach.agents.schemas import ExerciseAdjustment, NutritionAdvice, WorkoutAdvice
from app.coach.agents.validate import resolve_conflicts, validate_nutrition, validate_workout

Answer = Mapping[str, Any] | str | Callable[[AgentTask[Any]], Any]


class ScriptedModel:
    """Answers each agent from a script (one entry per call, the last repeating); records what it saw."""

    name = "scripted"

    def __init__(self, **script: list[Answer]) -> None:
        self.script = script
        self.calls: dict[str, list[Mapping[str, Any]]] = {"nutrition": [], "workout": [], "reviewer": []}

    async def generate(self, task: AgentTask[Any]) -> ModelReply:
        calls = self.calls[task.agent]
        calls.append(task.context)
        answers = self.script[task.agent]
        answer = answers[min(len(calls), len(answers)) - 1]
        return ModelReply(answer(task) if callable(answer) else answer)


def snapshot(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "avg_calories": 2000.0,
        "target_calories": 2200,
        "target_version": 1,
        "adherence_percent": 100.0,
        "complete_days": 6,
        "partial_days": 0,
        "missing_days": 0,
        "target_gap_kcal": -1200,
        "weigh_ins": 2,
        "weight_change_kg": -0.2,
        "goal_rate_kg_per_week": 0.0,
        "goal": "maintain",
        "workouts_done": 3,
        "workouts_planned": 3,
        "completion_percent": 100.0,
        "avg_rpe": 8.0,
        "routines": [
            {
                "routine_id": "r1",
                "name": "Push",
                "days": [0, 3],
                "exercises": [
                    {
                        "exercise_id": "bench",
                        "name": "Bench Press",
                        "working_sets": 3,
                        "target_weight_kg": 100.0,
                        "target_reps": 5,
                    },
                    {
                        "exercise_id": "dips",
                        "name": "Dips",
                        "working_sets": 3,
                        "target_weight_kg": None,
                        "target_reps": 10,
                    },
                ],
            }
        ],
        "exercise_trends": {},
        "equipment": ["barbell"],
    }
    return {**base, **overrides}


KEEP_NUTRITION = {"action": "keep", "headline": "Keep it", "evidence": ["Steady."]}
KEEP_WORKOUT = {"action": "keep", "headline": "Keep it", "evidence": ["Steady."]}
APPROVE = {"findings": [], "keep_nutrition": True, "keep_workout": True, "note": "Looks consistent."}


def cut_to(calories: int) -> dict[str, Any]:
    return {
        "action": "change",
        "new_calorie_target": calories,
        "headline": "Cut",
        "evidence": ["Trend is flat."],
    }


def adjust(*adjustments: tuple[str, str, float]) -> dict[str, Any]:
    return {
        "action": "change",
        "adjustments": [
            {
                "routine_id": "r1",
                "exercise_id": exercise,
                "field": field,
                "new_value": value,
                "reason": "Trend.",
            }
            for exercise, field, value in adjustments
        ],
        "headline": "Adjust training",
        "evidence": ["RPE is rising."],
    }


async def test_each_agent_sees_only_its_own_domain() -> None:
    model = ScriptedModel(nutrition=[KEEP_NUTRITION], workout=[KEEP_WORKOUT], reviewer=[APPROVE])
    await run_agents(snapshot(), model)

    nutrition_seen, workout_seen = model.calls["nutrition"][0], model.calls["workout"][0]
    assert "routines" not in nutrition_seen and "exercise_trends" not in nutrition_seen
    assert "avg_calories" not in workout_seen and "target_calories" not in workout_seen
    assert nutrition_seen == nutrition_context(snapshot())
    assert workout_seen == workout_context(snapshot())
    # The reviewer sees both proposals, each training change next to the value it replaces.
    assert set(model.calls["reviewer"][0]) >= {"nutrition", "workout", "current_calorie_target"}


async def test_a_nutrition_and_a_training_proposal_come_out_of_one_run() -> None:
    model = ScriptedModel(
        nutrition=[cut_to(2000)], workout=[adjust(("bench", "target_weight_kg", 95))], reviewer=[APPROVE]
    )
    draft = await run_agents(snapshot(), model)

    kinds = {proposal.kind: proposal for proposal in draft.proposals}
    assert kinds["nutrition"].changes[0].after == 2000
    training = kinds["training"].changes[0]
    assert (training.routine_id, training.exercise_id, training.field) == ("r1", "bench", "target_weight_kg")
    assert (training.before, training.after, training.unit) == (100.0, 95.0, "kg")
    assert [step["status"] for step in draft.pipeline] == ["done", "done", "done", "done", "waiting"]


async def test_the_reviewer_catches_less_food_with_more_training() -> None:
    # The fake model's own reviewer rule, given a cut alongside a load increase.
    model = ScriptedModel(
        nutrition=[cut_to(2000)],
        workout=[adjust(("bench", "target_weight_kg", 105))],
        reviewer=[lambda task: _fake_review(task.context)],
    )
    draft = await run_agents(snapshot(), model)

    assert [p.kind for p in draft.proposals] == ["nutrition"], "the load increase is held back"
    assert "recovery" in draft.proposals[0].reviewer_note
    assert draft.pipeline[3]["detail"] == "1 conflict resolved."


async def test_the_conflict_rule_holds_even_if_the_reviewer_misses_it() -> None:
    model = ScriptedModel(
        nutrition=[cut_to(2000)],
        workout=[adjust(("bench", "target_weight_kg", 105), ("bench", "working_sets", 2))],
        reviewer=[APPROVE],
    )
    draft = await run_agents(snapshot(), model)

    training = next(p for p in draft.proposals if p.kind == "training")
    assert [(c.field, c.after) for c in training.changes] == [("working_sets", 2.0)], (
        "only the decrease is kept"
    )
    assert "held back because the calorie target is going down" in training.reviewer_note


async def test_the_reviewer_can_hold_a_proposal_back_but_not_add_one() -> None:
    hold = {**APPROVE, "keep_workout": False, "note": "Not enough sessions to judge training."}
    model = ScriptedModel(
        nutrition=[KEEP_NUTRITION], workout=[adjust(("bench", "target_reps", 6))], reviewer=[hold]
    )
    draft = await run_agents(snapshot(), model)
    assert draft.proposals == []


async def test_invalid_structured_output_is_asked_for_again_then_given_up_on() -> None:
    model = ScriptedModel(
        nutrition=[{"action": "change", "headline": "Cut", "evidence": ["x"]}],  # no target: invalid
        workout=[adjust(("bench", "target_reps", 6))],
        reviewer=[APPROVE],
    )
    draft = await run_agents(snapshot(), model)

    assert len(model.calls["nutrition"]) == 2, "one retry, not an endless loop"
    assert [p.kind for p in draft.proposals] == ["training"], "the other agent's proposal still stands"
    assert draft.pipeline[1] == {
        "id": "nutrition",
        "title": "Nutrition agent",
        "detail": "Couldn't produce a valid proposal.",
        "status": "failed",
    }


async def test_a_second_attempt_that_parses_is_used() -> None:
    model = ScriptedModel(nutrition=["not json", cut_to(2000)], workout=[KEEP_WORKOUT], reviewer=[APPROVE])
    draft = await run_agents(snapshot(), model)
    assert draft.proposals[0].changes[0].after == 2000


async def test_extra_fields_in_agent_output_are_rejected() -> None:
    sneaky = {**KEEP_NUTRITION, "apply_immediately": True}
    model = ScriptedModel(nutrition=[sneaky], workout=[KEEP_WORKOUT], reviewer=[APPROVE])
    draft = await run_agents(snapshot(), model)
    assert draft.pipeline[1]["status"] == "failed"


async def test_without_a_review_the_validation_rules_still_apply() -> None:
    model = ScriptedModel(nutrition=[cut_to(1200)], workout=[KEEP_WORKOUT], reviewer=[{"oops": True}])
    draft = await run_agents(snapshot(), model)

    assert draft.proposals[0].changes[0].after == 1900, "still limited to a 300 kcal step"
    assert draft.pipeline[3]["status"] == "failed"


async def test_a_transient_model_error_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        graph_module,
        "MODEL_RETRY",
        RetryPolicy(max_attempts=3, initial_interval=0.01, jitter=False, retry_on=ModelUnavailableError),
    )

    def flaky(task: AgentTask[Any]) -> Any:
        raise ModelUnavailableError("rate limited")

    model = ScriptedModel(nutrition=[flaky, KEEP_NUTRITION], workout=[KEEP_WORKOUT], reviewer=[APPROVE])
    draft = await run_agents(snapshot(), model)

    assert len(model.calls["nutrition"]) == 2
    assert draft.pipeline[1]["status"] == "done"


async def test_every_model_call_is_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        graph_module,
        "MODEL_RETRY",
        RetryPolicy(max_attempts=3, initial_interval=0.01, jitter=False, retry_on=ModelUnavailableError),
    )

    def flaky(task: AgentTask[Any]) -> Any:
        raise ModelUnavailableError("rate limited")

    model = ScriptedModel(
        nutrition=[flaky, KEEP_NUTRITION], workout=["not json", KEEP_WORKOUT], reviewer=[APPROVE]
    )
    metrics = RunMetrics(model="scripted")
    await run_agents(snapshot(), model, metrics=metrics)

    summary = metrics.summary(outcome="completed", duration_ms=1234)
    assert (summary["outcome"], summary["model"], summary["resumed"]) == ("completed", "scripted", False)
    assert (summary["duration_ms"], summary["calls"]) == (1234, 5)
    agents = summary["agents"]
    assert (agents["nutrition"]["calls"], agents["nutrition"]["outcome"]) == (2, "valid")
    assert agents["nutrition"]["errors"] == ["ModelUnavailableError"], "the retried error, by class only"
    assert (agents["workout"]["calls"], agents["workout"]["outcome"], agents["workout"]["errors"]) == (
        2,
        "valid",
        [],
    )
    assert agents["reviewer"]["calls"] == 1
    assert [call.outcome for call in metrics.calls if call.agent == "workout"] == ["invalid", "valid"]


async def test_a_model_that_stays_down_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        graph_module,
        "MODEL_RETRY",
        RetryPolicy(max_attempts=2, initial_interval=0.01, jitter=False, retry_on=ModelUnavailableError),
    )

    def down(task: AgentTask[Any]) -> Any:
        raise ModelUnavailableError("down")

    model = ScriptedModel(nutrition=[down], workout=[KEEP_WORKOUT], reviewer=[APPROVE])
    with pytest.raises(ModelUnavailableError):
        await run_agents(snapshot(), model)
    assert len(model.calls["nutrition"]) == 2


async def test_an_interrupted_run_resumes_from_its_checkpoint_without_redoing_finished_steps() -> None:
    def crash(task: AgentTask[Any]) -> Any:
        raise RuntimeError("worker died")

    saver = InMemorySaver()
    model = ScriptedModel(nutrition=[cut_to(2000)], workout=[crash, KEEP_WORKOUT], reviewer=[APPROVE])
    with pytest.raises(RuntimeError):
        await run_agents(snapshot(), model, thread_id="check-in-1", checkpointer=saver)
    assert len(model.calls["nutrition"]) == 1

    metrics = RunMetrics(model="scripted")
    draft = await run_agents(snapshot(), model, thread_id="check-in-1", checkpointer=saver, metrics=metrics)

    assert len(model.calls["nutrition"]) == 1, "the finished nutrition step was kept, not run again"
    assert metrics.resumed
    assert {call.agent for call in metrics.calls} == {"workout", "reviewer"}
    assert len(model.calls["workout"]) == 2
    assert draft.proposals[0].changes[0].after == 2000

    # A finished run is read back from its checkpoint, not run a third time.
    reread = RunMetrics(model="scripted")
    again = await run_agents(snapshot(), model, thread_id="check-in-1", checkpointer=saver, metrics=reread)
    assert again == draft
    assert len(model.calls["reviewer"]) == 1
    assert reread.resumed and reread.calls == [], "counted as resumed, not as a free fresh run"


async def test_too_little_data_is_reported_rather_than_a_change_invented() -> None:
    draft = await run_agents(
        snapshot(adherence_percent=57.0, complete_days=4, missing_days=3), FakeCoachModel()
    )
    assert all(p.kind != "nutrition" for p in draft.proposals)
    assert "more days" in draft.pipeline[1]["detail"]


# --- Deterministic validation -------------------------------------------------


def nutrition(target: int) -> NutritionAdvice:
    return NutritionAdvice.model_validate(cut_to(target))


@pytest.mark.parametrize(
    ("proposed", "current", "expected"),
    [
        (2100, 2200, 2100),
        (1500, 2200, 1900),  # limited to a 300 kcal step
        (3000, 2200, 2500),
        (900, 1100, 1000),  # never below the floor
        (6200, 5900, 6000),  # nor above the ceiling
        (2213, 2200, None),  # rounds back to the current target: no change
        (2130, 2000, 2150),  # rounded to the 50 kcal step
    ],
)
def test_calorie_targets_are_held_to_the_limits(proposed: int, current: int, expected: int | None) -> None:
    target, notes = validate_nutrition(nutrition(proposed), current)
    assert target == expected
    assert bool(notes) == (expected is not None and abs(proposed - expected) >= 50)


def workout(*adjustments: tuple[str, str, float]) -> WorkoutAdvice:
    return WorkoutAdvice.model_validate(adjust(*adjustments))


@pytest.mark.parametrize(
    ("field", "wanted", "expected"),
    [
        ("target_weight_kg", 102.5, 102.5),
        ("target_weight_kg", 130, 110.0),  # at most +10%
        ("target_weight_kg", 50, 90.0),  # at most -10%
        ("target_weight_kg", 96.3, 97.5),  # rounded to plates
        ("working_sets", 6, 4.0),  # one set at a time
        ("working_sets", 0, 2.0),
        ("target_reps", 12, 8.0),  # three reps at a time
    ],
)
def test_training_changes_are_held_to_the_limits(field: str, wanted: float, expected: float) -> None:
    kept, _ = validate_workout(workout(("bench", field, wanted)), snapshot()["routines"])
    assert [(a.field, a.before, a.after) for a in kept] == [
        (field, snapshot()["routines"][0]["exercises"][0][field], expected)
    ]


def test_training_changes_must_name_a_scheduled_exercise() -> None:
    kept, notes = validate_workout(workout(("squat", "target_reps", 6)), snapshot()["routines"])
    assert kept == []
    assert "isn't in your scheduled routines" in notes[0]


def test_a_target_that_isnt_set_is_not_invented() -> None:
    kept, notes = validate_workout(workout(("dips", "target_weight_kg", 10)), snapshot()["routines"])
    assert kept == []
    assert "has no target weight" in notes[0]


def test_the_same_target_is_changed_only_once() -> None:
    kept, _ = validate_workout(
        workout(("bench", "target_reps", 6), ("bench", "target_reps", 7)), snapshot()["routines"]
    )
    assert [a.after for a in kept] == [6.0]


def test_a_cut_holds_back_only_training_increases() -> None:
    kept, _ = validate_workout(
        workout(("bench", "target_weight_kg", 105), ("bench", "target_reps", 4)), snapshot()["routines"]
    )
    held, notes = resolve_conflicts(2000, 2200, kept)
    assert [(a.field, a.after) for a in held] == [("target_reps", 4.0)]
    assert notes
    assert resolve_conflicts(2400, 2200, kept) == (kept, []), "a raise in calories is no conflict"


def test_adjustment_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        ExerciseAdjustment.model_validate(
            {
                "routine_id": "r1",
                "exercise_id": "bench",
                "field": "rest_seconds",
                "new_value": 60,
                "reason": "x",
            }
        )


def test_a_calorie_target_off_the_50_kcal_grid_still_moves_at_most_300() -> None:
    target, _ = validate_nutrition(nutrition(3000), 2375)
    assert target == 2650  # 2675 is the limit; rounding goes inwards, never to 2700
    target, _ = validate_nutrition(nutrition(1000), 2375)
    assert target == 2100  # 2075 is the limit; rounds up to 2100, not down past it


@pytest.mark.parametrize(("before", "wanted"), [(4.0, 3.8), (4.0, 10.0), (2.0, 5.0), (1.0, 0.0)])
def test_a_light_weight_with_no_plate_step_inside_the_limit_is_left_alone(
    before: float, wanted: float
) -> None:
    routines = snapshot()["routines"]
    routines[0]["exercises"][0]["target_weight_kg"] = before
    kept, _ = validate_workout(workout(("bench", "target_weight_kg", wanted)), routines)
    assert kept == []


async def test_a_cut_the_reviewer_held_back_does_not_hold_back_training() -> None:
    hold_cut = {**APPROVE, "keep_nutrition": False, "note": "Weight data is too thin for a cut."}
    model = ScriptedModel(
        nutrition=[cut_to(2000)], workout=[adjust(("bench", "target_weight_kg", 102.5))], reviewer=[hold_cut]
    )
    draft = await run_agents(snapshot(), model)

    assert [p.kind for p in draft.proposals] == ["training"]
    assert draft.proposals[0].changes[0].after == 102.5
    assert "calorie target is going down" not in draft.proposals[0].reviewer_note


async def test_a_snapshot_taken_before_training_data_was_gathered_still_runs() -> None:
    old = {
        key: value
        for key, value in snapshot().items()
        if key not in ("routines", "exercise_trends", "equipment")
    }
    draft = await run_agents(old, FakeCoachModel())
    assert draft.pipeline[2]["status"] == "done"
    assert all(p.kind != "training" for p in draft.proposals)
