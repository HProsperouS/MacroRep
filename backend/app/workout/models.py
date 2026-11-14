"""Exercise catalog, routines, weekly schedule, and logged sessions."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence import Base, TimestampMixin
from app.shared.validation import MAX_EXERCISE_NOTE_LENGTH

EQUIPMENT = ("barbell", "dumbbell", "cable", "machine", "bodyweight", "kettlebell", "band")
# Where an exercise comes from: the user's own ("custom") or the shared library (see Exercise.source).
EXERCISE_SOURCES = ("custom", "library")
MUSCLE_GROUPS = (
    "chest",
    "back",
    "shoulders",
    "biceps",
    "triceps",
    "quads",
    "hamstrings",
    "glutes",
    "calves",
    "core",
)


class SetKind(StrEnum):
    WARMUP = "warmup"
    WORKING = "working"
    FAILURE = "failure"
    DROP = "drop"


class Exercise(TimestampMixin, Base):
    """An exercise from the shared library, or a user's private custom one."""

    __tablename__ = "exercises"
    __table_args__ = (Index("ix_exercises_owner_name", "owner_id", "name"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    equipment: Mapped[str] = mapped_column(SAEnum(*EQUIPMENT, name="equipment"), nullable=False)
    muscles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    @property
    def source(self) -> str:
        return "custom" if self.owner_id else "library"


class ExerciseNote(TimestampMixin, Base):
    """A user's own note on an exercise, e.g. "seat on 4". One per user and exercise, so it
    follows the exercise into every routine and freestyle workout."""

    __tablename__ = "exercise_notes"
    __table_args__ = (Index("uq_exercise_notes_owner_exercise", "owner_id", "exercise_id", unique=True),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(String(MAX_EXERCISE_NOTE_LENGTH), nullable=False)


class WorkoutPlanEntry(TimestampMixin, Base):
    """A routine: a named, reusable workout with its exercises (see ``WorkoutPlanExercise``).

    The table keeps its original name from when each weekday held its own plan.
    Which weekdays a routine is done on is ``WorkoutScheduleDay``'s business.
    """

    __tablename__ = "workout_plan_entries"
    __table_args__ = (Index("ix_workout_plan_entries_owner", "owner_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class WorkoutScheduleDay(Base):
    """The routine a user does on one day of the week (0=Monday .. 6=Sunday). No row means a rest day."""

    __tablename__ = "workout_schedule_days"
    __table_args__ = (Index("uq_workout_schedule_owner_day", "owner_id", "day_of_week", unique=True),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    routine_id: Mapped[str] = mapped_column(
        ForeignKey("workout_plan_entries.id", ondelete="CASCADE"), nullable=False
    )


class WorkoutPlanExercise(Base):
    """One exercise within a routine, in display order."""

    __tablename__ = "workout_plan_exercises"
    __table_args__ = (Index("ix_workout_plan_exercises_entry", "plan_entry_id", "position"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    plan_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workout_plan_entries.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rest_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    # Each item: {"kind": "warmup"|"working", "target_weight_kg": float | None, "target_reps": int | None}
    planned_sets: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)


class WorkoutSession(TimestampMixin, Base):
    """A finished (logged) workout."""

    __tablename__ = "workout_sessions"
    __table_args__ = (Index("ix_workout_sessions_owner_started", "owner_id", "started_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("workout_plan_entries.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # The lifter's latest weigh-in when the workout was logged: what a bodyweight set's load
    # counts it as. Kept with the workout so later weigh-ins don't rewrite its history.
    body_weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)


class WorkoutSetLog(Base):
    """One completed set, kept queryable per exercise for progression lookups."""

    __tablename__ = "workout_set_logs"
    __table_args__ = (Index("ix_workout_set_logs_exercise", "owner_id", "exercise_id", "position"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exercise_id: Mapped[str | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="SET NULL"), nullable=True
    )
    exercise_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[SetKind] = mapped_column(SAEnum(SetKind, name="set_kind"), nullable=False)
    # What was typed: the plates, the added weight on a bodyweight move, a band's guess.
    weight_kg: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    # What volume, estimated 1RM and PRs are worked out from (app.analytics.training
    # .effective_load_kg): bodyweight added for bodyweight moves, 0 for bands (tracked by reps).
    load_kg: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    # Rating of Perceived Exertion, 1-10 in 0.5 steps. Nullable — logging it is optional.
    rpe: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Order of the exercise within the session. Null on sets logged before this was stored.
    exercise_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
