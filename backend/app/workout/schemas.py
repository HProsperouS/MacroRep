"""Workout catalog and session API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.shared.schema import CamelModel, validate_choice

from .models import EQUIPMENT, SetKind


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
    name: str = Field(min_length=1, max_length=255)
    equipment: str
    muscles: list[str] = Field(min_length=1)

    @field_validator("equipment")
    @classmethod
    def check_equipment(cls, value: str) -> str:
        return validate_choice(value, EQUIPMENT, "equipment")


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
    weight_kg: float = Field(ge=0)
    reps: int = Field(ge=0)
    rpe: float | None = Field(default=None, ge=1, le=10, multiple_of=0.5)


class FinishWorkoutExercise(CamelModel):
    exercise_id: str
    name: str
    sets: list[LoggedSet]


class FinishWorkoutInput(CamelModel):
    plan_id: str | None
    name: str = Field(min_length=1, max_length=255)
    started_at: datetime
    finished_at: datetime
    exercises: list[FinishWorkoutExercise]


class WorkoutSummary(CamelModel):
    id: str
    name: str
    duration_seconds: int
    sets_completed: int
    volume_kg: float
    personal_records: list[str]


class PlanSetInput(CamelModel):
    kind: SetKind
    target_weight_kg: float | None = Field(default=None, ge=0)
    target_reps: int | None = Field(default=None, ge=1)


class PlanExerciseInput(CamelModel):
    exercise_id: str
    rest_seconds: int = Field(ge=0, le=600)
    sets: list[PlanSetInput] = Field(min_length=1)


class SavePlanDayInput(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    week_label: str = Field(min_length=1, max_length=64)
    estimated_minutes: int = Field(ge=1, le=600)
    exercises: list[PlanExerciseInput] = Field(min_length=1)


class WeekPlanDay(CamelModel):
    """A user's plan for one day of the week (0=Monday .. 6=Sunday); `plan` is
    null for a rest day (no `WorkoutPlanEntry` saved for that day)."""

    day_of_week: int
    plan: PlannedWorkout | None
