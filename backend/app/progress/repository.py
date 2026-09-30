"""Cross-domain read queries backing the progress dashboard.

Progress owns no tables of its own — it is a read-model over food, workout,
body, and coach data — so its queries live here rather than scattered as
progress-specific methods bolted onto every other domain's repository.

Date ranges are the user's local calendar days. Food and weigh-in dates are
already local; timestamps (workouts, check-ins) are matched through
``utc_bounds`` and dated with ``local_date`` in the user's zone.
"""

from __future__ import annotations

from datetime import date as date_
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.training import estimated_one_rep_max, weekly_volume_kg
from app.body.models import WeighIn
from app.coach.models import CheckIn
from app.food.models import FoodEntry
from app.shared.timezones import local_date, utc_bounds
from app.workout.models import SetKind, WorkoutPlanEntry, WorkoutSession, WorkoutSetLog


class ProgressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def weigh_ins_up_to(self, owner_id: str, up_to: date_) -> list[WeighIn]:
        statement = (
            select(WeighIn)
            .where(WeighIn.owner_id == owner_id, WeighIn.log_date <= up_to)
            .order_by(WeighIn.log_date.asc())
        )
        return list(await self.session.scalars(statement))

    async def daily_calories(self, owner_id: str, start: date_, end: date_) -> dict[date_, int]:
        statement = (
            select(FoodEntry.log_date, func.sum(FoodEntry.calories))
            .where(FoodEntry.owner_id == owner_id, FoodEntry.log_date >= start, FoodEntry.log_date <= end)
            .group_by(FoodEntry.log_date)
        )
        rows = await self.session.execute(statement)
        return {row[0]: int(row[1] or 0) for row in rows}

    async def workouts_done(self, owner_id: str, start: date_, end: date_, zone: ZoneInfo) -> int:
        since, until = utc_bounds(start, end, zone)
        statement = select(func.count()).where(
            WorkoutSession.owner_id == owner_id,
            WorkoutSession.started_at >= since,
            WorkoutSession.started_at < until,
        )
        return int(await self.session.scalar(statement) or 0)

    async def plan_weekdays(self, owner_id: str) -> set[int]:
        """Days of the week (0=Monday) with a planned workout."""

        statement = select(WorkoutPlanEntry.day_of_week).where(WorkoutPlanEntry.owner_id == owner_id)
        return set(await self.session.scalars(statement))

    async def rpe_entries(
        self, owner_id: str, start: date_, end: date_, zone: ZoneInfo
    ) -> list[tuple[date_, float]]:
        """(session date, RPE) for each working set with an RPE logged."""

        since, until = utc_bounds(start, end, zone)
        statement = (
            select(WorkoutSetLog.rpe, WorkoutSession.started_at)
            .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
            .where(
                WorkoutSetLog.owner_id == owner_id,
                WorkoutSetLog.kind == SetKind.WORKING,
                WorkoutSetLog.rpe.is_not(None),
                WorkoutSession.started_at >= since,
                WorkoutSession.started_at < until,
            )
        )
        rows = await self.session.execute(statement)
        return [(local_date(started_at, zone), float(rpe)) for rpe, started_at in rows]

    async def weekly_volume(
        self, owner_id: str, start: date_, end: date_, zone: ZoneInfo
    ) -> dict[date_, float]:
        """Working-set volume (kg) per week, keyed by the week's Monday."""

        since, until = utc_bounds(start, end, zone)
        statement = (
            select(WorkoutSetLog.weight_kg, WorkoutSetLog.reps, WorkoutSession.started_at)
            .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
            .where(
                WorkoutSetLog.owner_id == owner_id,
                WorkoutSetLog.kind == SetKind.WORKING,
                WorkoutSession.started_at >= since,
                WorkoutSession.started_at < until,
            )
        )
        rows = await self.session.execute(statement)
        return weekly_volume_kg(
            (local_date(started_at, zone), float(weight_kg), reps) for weight_kg, reps, started_at in rows
        )

    async def strength_lifts(
        self, owner_id: str, start: date_, end: date_, zone: ZoneInfo
    ) -> dict[str, tuple[float, float]]:
        """Best estimated 1RM per exercise at the start vs. the end of the range."""

        _, until = utc_bounds(start, end, zone)
        statement = (
            select(
                WorkoutSetLog.exercise_name,
                WorkoutSetLog.weight_kg,
                WorkoutSetLog.reps,
                WorkoutSession.started_at,
            )
            .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
            .where(
                WorkoutSetLog.owner_id == owner_id,
                WorkoutSetLog.kind == SetKind.WORKING,
                WorkoutSession.started_at < until,
            )
        )
        rows = await self.session.execute(statement)
        before: dict[str, float] = {}
        current: dict[str, float] = {}
        midpoint = start
        for name, weight_kg, reps, started_at in rows:
            e1rm = estimated_one_rep_max(float(weight_kg), reps)
            if e1rm is None:
                continue
            bucket = before if local_date(started_at, zone) < midpoint else current
            bucket[name] = max(bucket.get(name, 0.0), e1rm)
        return {name: (before.get(name, current[name]), current[name]) for name in current}

    async def check_ins_in_range(
        self, owner_id: str, start: date_, end: date_, zone: ZoneInfo
    ) -> list[CheckIn]:
        since, until = utc_bounds(start, end, zone)
        statement = (
            select(CheckIn)
            .where(
                CheckIn.owner_id == owner_id,
                CheckIn.created_utc >= since,
                CheckIn.created_utc < until,
            )
            .order_by(CheckIn.created_utc.asc())
        )
        return list(await self.session.scalars(statement))
