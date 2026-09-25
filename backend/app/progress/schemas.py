"""Progress dashboard API contracts (a read-model over other domains)."""

from __future__ import annotations

from datetime import date as date_
from typing import Literal

from pydantic import Field

from app.body.schemas import WeightPoint as WeightPoint
from app.shared.schema import CamelModel

ProgressRange = Literal["1M", "3M", "6M", "1Y", "All"]


class WeightSummary(CamelModel):
    points: list[WeightPoint]
    current_trend_kg: float
    change_kg: float
    rate_per_week_kg: float
    goal_rate_per_week_kg: float


class VolumeWeek(CamelModel):
    week_start: date_
    tonnes: float


class VolumeSummary(CamelModel):
    weeks: list[VolumeWeek]
    # Mean of the weeks in range: a reference line, not a goal anyone set.
    average_tonnes: float
    # A weekly volume goal (e.g. derived from the workout plan). Always null
    # for now; clients show `average_tonnes` as their reference until it's set.
    target_tonnes: float | None = None
    # The most recent *completed* Monday-Sunday week, so a half-finished
    # current week never reads as a drop.
    last_week_tonnes: float
    # last_week_tonnes vs the week before it; null when the week before had no volume.
    change_percent: float | None


class StrengthLift(CamelModel):
    exercise: str
    estimated1_rm_kg: float
    change_kg: float


class WorkoutsSummary(CamelModel):
    done: int
    planned: int


class CheckInHistoryItem(CamelModel):
    id: str
    week_label: str
    date: date_
    summary: str
    outcome: str


class ProgressResponse(CamelModel):
    range: ProgressRange
    date_from: date_ = Field(alias="from")
    date_to: date_ = Field(alias="to")
    weight: WeightSummary
    expenditure_kcal_per_day: float
    adherence_percent: float
    workouts: WorkoutsSummary
    volume: VolumeSummary
    strength: list[StrengthLift]
    check_ins: list[CheckInHistoryItem]


class DailyCalories(CamelModel):
    date: date_
    calories: int
