"""Structured output each agent must return. Anything that doesn't parse is rejected."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.shared.validation import MAX_NAME_LENGTH


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


ChatIntent = Literal[
    "explain", "adjust_nutrition", "adjust_workout", "start_check_in", "out_of_scope", "medical"
]


class ChatReply(_AgentOutput):
    """Coach Chat's turn: what the user wants, and what to say.

    For a change asked for clearly enough, ``request`` restates it for the agent that
    revises the proposal. For one that isn't, ``request`` stays empty and ``reply`` asks one
    question about what's missing.
    """

    intent: ChatIntent
    reply: str = Field(min_length=1, max_length=800)
    request: str | None = Field(default=None, min_length=1, max_length=300)

    @field_validator("request", mode="before")
    @classmethod
    def blank_request_is_none(cls, value: object) -> object:
        """Models often send "" for "no request yet" rather than leaving it out."""

        return None if isinstance(value, str) and not value.strip() else value


class PhotoItem(_AgentOutput):
    """One food or drink seen in a photo, with its estimated portion and nutrition."""

    # As long as a food-log entry's name can be, so an item logs as it came.
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    # How the portion looks, e.g. "1 cup" or "half a plate".
    portion: str = Field(min_length=1, max_length=60)
    grams: float = Field(gt=0, le=3_000)
    calories: int = Field(ge=0, le=5_000)
    protein: float = Field(ge=0, le=500)
    carbs: float = Field(ge=0, le=500)
    fat: float = Field(ge=0, le=500)


class PhotoEstimate(_AgentOutput):
    """What a meal photo seems to hold. No items means no food was recognised."""

    items: list[PhotoItem] = Field(default_factory=list, max_length=12)
    # What's uncertain (hidden oil, sauces, a hard-to-judge portion), or why nothing was found.
    note: str | None = Field(default=None, max_length=300)
