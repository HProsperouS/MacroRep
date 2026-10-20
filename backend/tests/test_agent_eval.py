"""The agent evaluation harness runs end to end; its real-model results live in docs/."""

from __future__ import annotations

from typing import Any

from app.coach.agents.model import AgentTask, FakeCoachModel, ModelReply
from evals.agent_eval import SCENARIOS, calorie_direction, evaluate, report, training_direction, week


async def test_every_scenario_runs_and_is_reported() -> None:
    results = await evaluate(FakeCoachModel(), runs=1)

    assert len(results) == len(SCENARIOS)
    assert all(result.outcomes for result in results)
    text = report(results, "fake", runs=1)
    assert "| Runs where all three agents answered within the schema | 10/10 (100%) |" in text
    assert all(f"`{scenario.name}`" in text for scenario in SCENARIOS)


def test_directions_are_read_from_each_agents_own_answer() -> None:
    state = {
        "snapshot": week(),
        "nutrition": {"action": "change", "new_calorie_target": 2000},
        "workout": {
            "adjustments": [
                {"exercise_id": "bench", "field": "target_weight_kg", "new_value": 82.5},
                {"exercise_id": "row", "field": "working_sets", "new_value": 2},
            ]
        },
    }
    assert calorie_direction(state) == "down"
    assert (training_direction(state, "bench"), training_direction(state, "row")) == ("up", "down")
    assert calorie_direction({"snapshot": week(), "nutrition": None}) is None


class BrokenModel:
    name = "broken"

    async def generate(self, task: AgentTask[Any]) -> ModelReply:
        raise RuntimeError("down")


async def test_a_failed_check_in_is_reported_without_losing_the_others() -> None:
    results = await evaluate(BrokenModel(), runs=1)

    assert all(result.error == "RuntimeError" for result in results)
    assert all(passed is False for result in results for passed in result.outcomes.values())
    text = report(results, "broken", runs=1)
    assert "| Runs where all three agents answered within the schema | 0/10 (0%) |" in text
    assert "`cut-stalled`: the check-in failed (RuntimeError)" in text
