"""Structured output each agent must return. Anything that doesn't parse is rejected."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _AgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NutritionAdvice(_AgentOutput):
    action: Literal["keep", "change"]
    # The proposed daily calorie target; required when action is "change".
    new_calorie_target: int | None = Field(default=None, ge=0, le=20_000)
    headline: str = Field(min_length=1, max_length=120)
    evidence: list[str] = Field(min_length=1, max_length=5)
    # What the data can't tell, e.g. "Only 4 days were logged".
    uncertainty: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def check_target(self) -> NutritionAdvice:
        if self.action == "change" and self.new_calorie_target is None:
            raise ValueError("a change needs new_calorie_target")
        return self


class ExerciseAdjustment(_AgentOutput):
    routine_id: str = Field(min_length=1, max_length=64)
    exercise_id: str = Field(min_length=1, max_length=64)
    field: Literal["working_sets", "target_weight_kg", "target_reps"]
    new_value: float = Field(ge=0, le=1_000)
    reason: str = Field(min_length=1, max_length=200)


class WorkoutAdvice(_AgentOutput):
    action: Literal["keep", "change"]
    adjustments: list[ExerciseAdjustment] = Field(default_factory=list, max_length=10)
    headline: str = Field(min_length=1, max_length=120)
    evidence: list[str] = Field(min_length=1, max_length=5)
    uncertainty: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def check_adjustments(self) -> WorkoutAdvice:
        if self.action == "change" and not self.adjustments:
            raise ValueError("a change needs at least one adjustment")
        return self


class ReviewFinding(_AgentOutput):
    severity: Literal["info", "warning", "conflict"]
    message: str = Field(min_length=1, max_length=300)


class Review(_AgentOutput):
    findings: list[ReviewFinding] = Field(default_factory=list, max_length=10)
    # The reviewer can hold a proposal back, never add or enlarge one.
    keep_nutrition: bool
    keep_workout: bool
    note: str = Field(min_length=1, max_length=400)


class ChatReply(_AgentOutput):
    """Coach Chat's answer. The topic says what kind of question it was, so out-of-scope and
    medical questions can be counted; only the reply is shown."""

    topic: Literal["check_in", "progress", "nutrition", "training", "out_of_scope", "medical"]
    reply: str = Field(min_length=1, max_length=800)
