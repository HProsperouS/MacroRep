"""Progress dashboard API contracts (a read-model over other domains)."""

from __future__ import annotations

from datetime import date as date_
from typing import Literal

from pydantic import Field

from app.analytics.nutrition import DayStatus
from app.body.schemas import WeightPoint as WeightPoint
from app.shared.schema import CamelModel

ProgressRange = Literal["1M", "3M", "6M", "1Y", "All"]


class WeightSummary(CamelModel):
    points: list[WeightPoint]
    # None until there's a weigh-in.
    current_trend_kg: float | None
    change_kg: float
    # Null until weigh-ins cover a week.
    rate_per_week_kg: float | None
    goal_rate_per_week_kg: float


class VolumeWeek(CamelModel):
    week_start: date_
    tonnes: float
    # Mean RPE of the week's working sets with an RPE logged; null if none was.
    avg_rpe: float | None = None


class VolumeSummary(CamelModel):
    weeks: list[VolumeWeek]
    # Mean of the weeks in range: a reference line, not a goal anyone set.
    average_tonnes: float
    # The most recent *completed* Monday-Sunday week, so a half-finished
    # current week never reads as a drop.
    last_week_tonnes: float
    # last_week_tonnes vs the week before it; null when the week before had no volume.
    change_percent: float | None


class StrengthLift(CamelModel):
    exercise: str
    estimated1_rm_kg: float
    change_kg: float


class RpeSummary(CamelModel):
    # The current Monday-Sunday week so far; null until a set with an RPE is logged.
    this_week_avg: float | None
    # RPE points vs last week (e.g. +0.5); null unless both weeks have RPE logged.
    change: float | None


class WorkoutsSummary(CamelModel):
    # Every logged session, planned or not.
    done: int
    # Plan days that fell due in the range; today only once trained.
    planned: int
    # done / planned, not capped at 100; null with nothing planned.
    completion_percent: float | None


class CheckInHistoryItem(CamelModel):
    id: str
    week_label: str
    date: date_
    summary: str
    outcome: str


class LoggingSummary(CamelModel):
    """Finished days since the user signed up: today is still being logged and isn't
    counted, and days before the account existed weren't missed."""

    complete_days: int
    partial_days: int
    # Logged days within ±10% of the calorie target; null with nothing logged.
    target_adherence_percent: float | None
    # Intake minus target summed over logged days: negative means under target.
    target_gap_kcal: int


class ProgressResponse(CamelModel):
    range: ProgressRange
    date_from: date_ = Field(alias="from")
    date_to: date_ = Field(alias="to")
    weight: WeightSummary
    # Share of finished days since sign-up with any food logged; null before there's one.
    adherence_percent: float | None
    logging: LoggingSummary
    workouts: WorkoutsSummary
    volume: VolumeSummary
    rpe: RpeSummary
    strength: list[StrengthLift]
    check_ins: list[CheckInHistoryItem]


class DailyCalories(CamelModel):
    date: date_
    calories: int
    status: DayStatus
    # The calorie target in effect on this day, which can differ from today's.
    target_calories: int


class DailyCaloriesResponse(CamelModel):
    days: list[DailyCalories]
    # Today's target.
    target_calories: int
    # Intake minus target over the finished logged days: negative means under target.
    target_gap_kcal: int
