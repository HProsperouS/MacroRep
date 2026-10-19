"""The seam between the agents and a language model.

An agent hands the model an ``AgentTask``: its role, its instructions, a compact
JSON context, and the output schema. The model answers with raw structured output,
which the caller validates against the schema; a model can't skip validation.

Only ``FakeCoachModel`` exists for now: a deterministic stand-in with simple rules,
so the whole flow runs and is testable without an API key. A real provider is one
more class with the same ``generate`` method, picked by ``COACH_MODEL_PROVIDER``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)
AgentName = Literal["nutrition", "workout", "reviewer"]


class ModelUnavailableError(Exception):
    """A transient failure talking to the model (timeout, rate limit, 5xx): worth retrying."""


@dataclass(frozen=True)
class AgentTask(Generic[T]):
    agent: AgentName
    instructions: str
    context: Mapping[str, Any]
    output: type[T]


class CoachModel(Protocol):
    async def generate(self, task: AgentTask[T]) -> Mapping[str, Any] | str:
        """Raw structured output for ``task``: a JSON object, or JSON text."""
        ...


class FakeCoachModel:
    """Rule-based answers in the shape a real model would give. Not a good coach:
    it exists so the graph, validation and approval flow run end to end."""

    async def generate(self, task: AgentTask[T]) -> Mapping[str, Any]:
        if task.agent == "nutrition":
            return _fake_nutrition(task.context)
        if task.agent == "workout":
            return _fake_workout(task.context)
        return _fake_review(task.context)


def get_coach_model() -> CoachModel:
    provider = get_settings().coach_model_provider
    if provider == "fake":
        return FakeCoachModel()
    raise ValueError(f"Unknown COACH_MODEL_PROVIDER: {provider}")


# Kcal per kg/week of difference between the goal rate and the actual trend, for the fake's
# rough correction (about 7700 kcal per kg, spread over a week).
_KCAL_PER_KG_PER_WEEK = 1_100


def _fake_nutrition(context: Mapping[str, Any]) -> dict[str, Any]:
    target = int(context["target_calories"])
    avg = float(context["avg_calories"])
    adherence = float(context["adherence_percent"])
    change = float(context["weight_change_kg"])
    goal_rate = float(context["goal_rate_kg_per_week"])
    evidence = [
        f"Trend weight changed {change:+.2f} kg against a {goal_rate:+.2f} kg/week goal.",
        f"Food was logged on {adherence:.0f}% of days.",
        f"Logged days came to {int(context['target_gap_kcal']):+,} kcal against target in total.",
    ]
    if adherence < 80:
        return {
            "action": "keep",
            "headline": "Keep the calorie target until more days are logged",
            "evidence": evidence,
            "uncertainty": "Too few days were logged to judge intake reliably.",
        }
    if abs(change - goal_rate) < 0.15:
        return {"action": "keep", "headline": "On track: keep the calorie target", "evidence": evidence}
    new_target = round(target - (avg - target) + (goal_rate - change) * _KCAL_PER_KG_PER_WEEK)
    return {
        "action": "change",
        "new_calorie_target": new_target,
        "headline": f"Adjust the daily target to about {new_target:,} kcal",
        "evidence": evidence,
    }


def _fake_workout(context: Mapping[str, Any]) -> dict[str, Any]:
    trends: Mapping[str, Mapping[str, Any]] = context["exercise_trends"]
    adjustments: list[dict[str, Any]] = []
    evidence: list[str] = []
    for routine in context["routines"]:
        for exercise in routine["exercises"]:
            trend = trends.get(exercise["exercise_id"])
            weight = exercise["target_weight_kg"]
            if trend is None or weight is None or trend["recent_avg_rpe"] is None:
                continue
            recent, prior, rpe = (
                trend["recent_best_e1rm_kg"],
                trend["prior_best_e1rm_kg"],
                trend["recent_avg_rpe"],
            )
            stalled = recent is not None and prior is not None and recent <= prior
            if rpe >= 9 and stalled:
                new_weight, why = weight * 0.95, f"RPE {rpe:.1f} with no strength gain: ease off"
            elif rpe <= 7.5 and not stalled and trend["recent_sessions"] > 0:
                new_weight, why = weight + 2.5, f"RPE {rpe:.1f} and still progressing: add load"
            else:
                continue
            adjustments.append(
                {
                    "routine_id": routine["routine_id"],
                    "exercise_id": exercise["exercise_id"],
                    "field": "target_weight_kg",
                    "new_value": new_weight,
                    "reason": why,
                }
            )
            evidence.append(f"{exercise['name']}: {why}.")
    completion = context["completion_percent"]
    done = f"{context['workouts_done']}/{context['workouts_planned']} planned workouts done"
    evidence.append(done + (f" ({completion:.0f}%)." if completion is not None else "."))
    if not adjustments:
        return {"action": "keep", "headline": "Keep the training plan as it is", "evidence": evidence[-1:]}
    return {
        "action": "change",
        "adjustments": adjustments[:3],
        "headline": "Adjust training loads to how the lifts are going",
        "evidence": evidence[:5],
    }


def _fake_review(context: Mapping[str, Any]) -> dict[str, Any]:
    nutrition: Mapping[str, Any] | None = context["nutrition"]
    workout: Mapping[str, Any] | None = context["workout"]
    findings: list[dict[str, str]] = []
    cutting = (
        nutrition is not None
        and nutrition["action"] == "change"
        and nutrition["new_calorie_target"] < context["current_calorie_target"]
    )
    loading = workout is not None and any(
        adjustment["new_value"] > adjustment["current_value"] for adjustment in workout["adjustments"]
    )
    if cutting and loading:
        findings.append(
            {
                "severity": "conflict",
                "message": "Eating less while training harder risks poor recovery: hold the load increases.",
            }
        )
    if context["missing_days"] > 2:
        findings.append({"severity": "warning", "message": "Several days have no food logged."})
    note = (
        findings[0]["message"] if findings else "The proposals are consistent with each other and the data."
    )
    return {
        "findings": findings,
        "keep_nutrition": True,
        "keep_workout": not (cutting and loading),
        "note": note,
    }
