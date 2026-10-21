"""The seam between the agents and a language model.

An agent hands the model an ``AgentTask``: its role, its instructions, a compact
JSON context, and the output schema. The model answers with raw structured output,
which the caller validates against the schema; a model can't skip validation.

``FakeCoachModel`` is a deterministic stand-in with simple rules, so the whole flow runs
and is testable without an API key. ``OpenAICoachModel`` asks OpenAI for the same output.
``COACH_MODEL_PROVIDER`` picks one.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Generic, Literal, Protocol, TypeVar

import openai
from openai.types.shared import ReasoningEffort
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
AgentName = Literal["nutrition", "workout", "reviewer", "chat"]


class ModelUnavailableError(Exception):
    """A transient failure talking to the model (timeout, rate limit, 5xx): worth retrying."""


@dataclass(frozen=True)
class AgentTask(Generic[T]):
    agent: AgentName
    instructions: str
    context: Mapping[str, Any]
    output: type[T]


@dataclass(frozen=True)
class ModelReply:
    """Raw output, with the tokens it took when the provider reports them."""

    output: Mapping[str, Any] | str
    input_tokens: int = 0
    output_tokens: int = 0


class CoachModel(Protocol):
    # Recorded with each run, e.g. "fake" or "openai/gpt-5.4-mini".
    name: str

    async def generate(self, task: AgentTask[T]) -> ModelReply:
        """Raw structured output for ``task`` (a JSON object, or JSON text) and its tokens."""
        ...


class FakeCoachModel:
    """Rule-based answers in the shape a real model would give. Not a good coach:
    it exists so the graph, validation and approval flow run end to end."""

    name = "fake"

    async def generate(self, task: AgentTask[T]) -> ModelReply:
        if "user_request" in task.context and task.agent in ("nutrition", "workout"):
            return ModelReply(_fake_revision(task.context))
        if task.agent == "nutrition":
            return ModelReply(_fake_nutrition(task.context))
        if task.agent == "workout":
            return ModelReply(_fake_workout(task.context))
        if task.agent == "chat":
            return ModelReply(_fake_chat(task.context))
        return ModelReply(_fake_review(task.context))


class OpenAICoachModel:
    """Asks OpenAI's Chat Completions API for an answer in the task's output schema.

    The schema is sent non-strict: strict mode accepts only a subset of JSON Schema, and the
    caller validates every answer against the full schema anyway.
    """

    def __init__(
        self, client: openai.AsyncOpenAI, model: str, reasoning_effort: ReasoningEffort = None
    ) -> None:
        self.client = client
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.name = f"openai/{model}"

    async def generate(self, task: AgentTask[T]) -> ModelReply:
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": task.instructions},
                    {"role": "user", "content": json.dumps(task.context, default=str)},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": task.output.__name__,
                        "schema": task.output.model_json_schema(),
                        "strict": False,
                    },
                },
                # Omitted, not sent as null, for a model without reasoning.
                reasoning_effort=self.reasoning_effort or openai.omit,
            )
        # A timeout is a connection error too.
        except openai.APIConnectionError as error:
            raise ModelUnavailableError(type(error).__name__) from error
        except openai.APIStatusError as error:
            # The statuses the SDK itself would retry. Anything else (a bad key, a bad request)
            # won't get better by asking again, so it fails the run.
            if error.status_code in _RETRYABLE_STATUSES or error.status_code >= 500:
                raise ModelUnavailableError(f"HTTP {error.status_code}") from error
            raise
        choice = completion.choices[0]
        if choice.finish_reason != "stop" or choice.message.refusal:
            # Cut off or refused: it is rejected like any answer that doesn't fit the schema.
            logger.warning(
                "model answer incomplete",
                extra={
                    "agent": task.agent,
                    "finish_reason": choice.finish_reason,
                    "refused": bool(choice.message.refusal),
                },
            )
        usage = completion.usage
        return ModelReply(
            output=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


_RETRYABLE_STATUSES = frozenset({408, 409, 429})


@lru_cache(maxsize=1)
def _openai_model(
    api_key: str, model: str, timeout_seconds: float, reasoning_effort: ReasoningEffort
) -> OpenAICoachModel:
    """One client per configuration, so its connection pool is reused across check-ins."""

    # LangGraph's retry policy does the retrying, with the step's own time limit.
    client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)
    return OpenAICoachModel(client, model, reasoning_effort)


def get_coach_model() -> CoachModel:
    settings = get_settings()
    if settings.coach_model_provider == "fake":
        return FakeCoachModel()
    key = settings.openai_api_key
    assert key is not None  # Settings refuses "openai" without a key
    return _openai_model(
        key.get_secret_value(),
        settings.openai_model,
        settings.openai_timeout_seconds,
        settings.openai_reasoning_effort,
    )


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


# Words the fake reads a chat message by, as the real model is told to: medical topics, and
# what a change to the calories or to a lift looks like.
_MEDICAL_WORDS = ("injur", "pain", "hurt", "medic", "doctor", "pregnan", "sick", "diagnos")
_CALORIE_WORDS = {"calorie", "calories", "kcal", "eat", "eating"}
_UP_WORDS = {"more", "raise", "increase", "higher", "heavier", "add"}
_DOWN_WORDS = {"less", "lower", "decrease", "reduce", "fewer", "lighter", "cut"}
_KEEP_WORDS = {"keep", "same"}


def _words(text: str) -> set[str]:
    """Whole words, so "great" isn't read as "eat"."""

    return set(re.findall(r"[a-z']+", text.lower()))


def _direction(text: str) -> str | None:
    words = _words(text)
    for direction, wanted in (("keep", _KEEP_WORDS), ("up", _UP_WORDS), ("down", _DOWN_WORDS)):
        if words & wanted:
            return direction
    return None


def _fake_chat(context: Mapping[str, Any]) -> dict[str, Any]:
    question = str(context["question"]).lower()
    if any(word.startswith(_MEDICAL_WORDS) for word in _words(question)):
        return {
            "intent": "medical",
            "reply": "I can't advise on that: please check with a doctor or physiotherapist. "
            "I can explain this week's proposals and how your training and eating went.",
        }
    exercises = [e["name"] for r in context["week"]["routines"] for e in r["exercises"]]
    lift = next((name for name in exercises if name.lower() in question), None)
    if _words(question) & _CALORIE_WORDS or lift:
        intent = "adjust_workout" if lift else "adjust_nutrition"
        if _direction(question) is None:
            ask = (
                f"Should {lift} go up, down or stay the same?"
                if lift
                else "More or fewer calories, and by about how much?"
            )
            return {"intent": intent, "reply": ask}
        return {"intent": intent, "reply": "I'll revise the proposal.", "request": context["question"]}
    proposals: list[Mapping[str, Any]] = context["proposals"]
    if proposals and ("why" in question or "change" in question):
        proposal = proposals[0]
        return {"intent": "explain", "reply": f"{proposal['headline']}. {' '.join(proposal['evidence'][:2])}"}
    return {"intent": "explain", "reply": str(context["week"]["summary"])}


def _fake_revision(context: Mapping[str, Any]) -> dict[str, Any]:
    """The fake's answer to a revision request: a fixed step in the direction asked."""

    request = str(context["user_request"])
    direction = _direction(request)
    evidence = [f"You asked: {request}"]
    if "target_calories" in context:
        if direction in (None, "keep"):
            return {"action": "keep", "headline": "Keep the calorie target as it is", "evidence": evidence}
        target = int(context["target_calories"]) + (100 if direction == "up" else -100)
        return {
            "action": "change",
            "new_calorie_target": target,
            "headline": "Revised target",
            "evidence": evidence,
        }
    for routine in context["routines"]:
        for exercise in routine["exercises"]:
            if exercise["name"].lower() in request.lower() and exercise["target_weight_kg"] is not None:
                if direction in (None, "keep"):
                    break
                weight = exercise["target_weight_kg"]
                new_weight = weight + 2.5 if direction == "up" else weight * 0.95
                adjustment = {
                    "routine_id": routine["routine_id"],
                    "exercise_id": exercise["exercise_id"],
                    "field": "target_weight_kg",
                    "new_value": new_weight,
                    "reason": f"You asked: {request}"[:200],
                }
                return {
                    "action": "change",
                    "adjustments": [adjustment],
                    "headline": "Revised load",
                    "evidence": evidence,
                }
    return {"action": "keep", "headline": "Keep training as it is", "evidence": evidence}
