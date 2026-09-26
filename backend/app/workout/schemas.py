"""Workout catalog and session API contracts."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.shared.schema import CamelModel, validate_choice
from app.shared.validation import (
    CLOCK_SKEW,
    MAX_EXERCISES_PER_WORKOUT,
    MAX_LABEL_LENGTH,
    MAX_NAME_LENGTH,
    MAX_REPS,
    MAX_SET_WEIGHT_KG,
    MAX_SETS_PER_EXERCISE,
    Identifier,
    PlainText,
    ensure_unique,
)

from .models import EQUIPMENT, MUSCLE_GROUPS, SetKind


class PreviousSet(CamelModel):
    weight_kg: float
    reps: int
    rpe: float | None = None


class LastSession(CamelModel):
    date: str
    sets: list[PreviousSet]


class ExerciseRead(CamelModel):
    id: str
    name: str
    equipment: str
    muscles: list[str]
    source: str
    last_session: LastSession | None = None


class CreateExerciseInput(CamelModel):
    name: PlainText = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    equipment: str
    muscles: list[str] = Field(min_length=1, max_length=len(MUSCLE_GROUPS))

    @field_validator("equipment")
    @classmethod
    def check_equipment(cls, value: str) -> str:
        return validate_choice(value, EQUIPMENT, "equipment")

    @field_validator("muscles")
    @classmethod
    def check_muscles(cls, value: list[str]) -> list[str]:
        return ensure_unique([validate_choice(item, MUSCLE_GROUPS, "muscles") for item in value], "muscles")


class PlannedSet(CamelModel):
    id: str
    kind: SetKind
    target_weight_kg: float | None = None
    target_reps: int | None = None
    previous: PreviousSet | None = None


class PlannedExercise(CamelModel):
    id: str
    name: str
    equipment: str
    muscles: str
    rest_seconds: int
    note: str | None = None
    tag: str | None = None
    sets: list[PlannedSet]


class StrengthHighlight(CamelModel):
    exercise: str
    estimated1_rm_kg: float
    change_kg: float
    period_label: str
    best_set: str


class PlannedWorkout(CamelModel):
    id: str
    name: str
    week_label: str
    estimated_minutes: int
    exercises: list[PlannedExercise]
    highlight: StrengthHighlight | None = None


class LoggedSet(CamelModel):
    kind: SetKind
    weight_kg: float = Field(ge=0, le=MAX_SET_WEIGHT_KG)
    # 0 is allowed: a failed attempt is still a set worth recording.
    reps: int = Field(ge=0, le=MAX_REPS)
    rpe: float | None = Field(default=None, ge=1, le=10, multiple_of=0.5)


class FinishWorkoutExercise(CamelModel):
    exercise_id: Identifier
    name: PlainText = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    sets: list[LoggedSet] = Field(min_length=1, max_length=MAX_SETS_PER_EXERCISE)


class FinishWorkoutInput(CamelModel):
    plan_id: Identifier | None
    name: PlainText = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    # Timezone-aware only: a naive time can't be placed on the timeline reliably.
    started_at: AwareDatetime
    finished_at: AwareDatetime
    exercises: list[FinishWorkoutExercise] = Field(min_length=1, max_length=MAX_EXERCISES_PER_WORKOUT)

    @model_validator(mode="after")
    def check_times(self) -> FinishWorkoutInput:
        # No upper limit on duration: a session left open overnight and
        # finished late is still a real workout, and rejecting it would lose it.
        if self.finished_at < self.started_at:
            raise ValueError("finishedAt must not be before startedAt")
        if self.finished_at > datetime.now(UTC) + CLOCK_SKEW:
            raise ValueError("a workout can't finish in the future")
        return self


class WorkoutSummary(CamelModel):
    id: str
    name: str
    duration_seconds: int
    sets_completed: int
    volume_kg: float
    personal_records: list[str]


class PlanSetInput(CamelModel):
    kind: SetKind
    target_weight_kg: float | None = Field(default=None, ge=0, le=MAX_SET_WEIGHT_KG)
    target_reps: int | None = Field(default=None, ge=1, le=MAX_REPS)


class PlanExerciseInput(CamelModel):
    exercise_id: Identifier
    rest_seconds: int = Field(ge=0, le=600)
    sets: list[PlanSetInput] = Field(min_length=1, max_length=MAX_SETS_PER_EXERCISE)


class SavePlanDayInput(CamelModel):
    name: PlainText = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    week_label: PlainText = Field(min_length=1, max_length=MAX_LABEL_LENGTH)
    estimated_minutes: int = Field(ge=1, le=600)
    exercises: list[PlanExerciseInput] = Field(min_length=1, max_length=MAX_EXERCISES_PER_WORKOUT)


class WeekPlanDay(CamelModel):
    """A user's plan for one day of the week (0=Monday .. 6=Sunday); `plan` is
    null for a rest day (no `WorkoutPlanEntry` saved for that day)."""

    day_of_week: int
    plan: PlannedWorkout | None
