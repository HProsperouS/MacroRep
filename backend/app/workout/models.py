"""Exercise catalog, weekly workout plan, and logged sessions."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence import Base, TimestampMixin

EQUIPMENT = ("barbell", "dumbbell", "cable", "machine", "bodyweight", "kettlebell", "band")
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


class WorkoutPlanEntry(TimestampMixin, Base):
    """A user's planned session for one day of the week (0=Monday .. 6=Sunday)."""

    __tablename__ = "workout_plan_entries"
    __table_args__ = (Index("uq_workout_plan_owner_day", "owner_id", "day_of_week", unique=True),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    week_label: Mapped[str] = mapped_column(String(64), nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)


class WorkoutPlanExercise(Base):
    """One exercise within a planned day, in display order."""

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
    weight_kg: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    # Rating of Perceived Exertion, 1-10 in 0.5 steps. Nullable — logging it is optional.
    rpe: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
