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
from datetime import timedelta
from typing import cast
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.training import average_rpe, estimated_one_rep_max, weekly_volume_kg
from app.body.models import WeighIn
from app.coach.models import CheckIn, CheckInStatus
from app.food.models import FoodEntry
from app.shared.timezones import local_date, utc_bounds
from app.workout.models import (
    Exercise,
    SetKind,
    WorkoutPlanEntry,
    WorkoutPlanExercise,
    WorkoutScheduleDay,
    WorkoutSession,
    WorkoutSetLog,
)
from app.workout.targets import routine_revision, working_targets

# How far back an exercise's recent performance is compared to, before the week under review.
_TREND_BASELINE_DAYS = 21


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

        statement = select(WorkoutScheduleDay.day_of_week).where(WorkoutScheduleDay.owner_id == owner_id)
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
                WorkoutSetLog.kind != SetKind.WARMUP,
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
                WorkoutSetLog.kind != SetKind.WARMUP,
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
                WorkoutSetLog.kind != SetKind.WARMUP,
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
        """Finished check-ins only: one still running or that failed has no outcome to show."""

        since, until = utc_bounds(start, end, zone)
        statement = (
            select(CheckIn)
            .where(
                CheckIn.owner_id == owner_id,
                CheckIn.created_utc >= since,
                CheckIn.created_utc < until,
                CheckIn.status.in_([CheckInStatus.NEEDS_REVIEW, CheckInStatus.REVIEWED]),
            )
            .order_by(CheckIn.created_utc.asc())
        )
        return list(await self.session.scalars(statement))

    async def scheduled_routines(self, owner_id: str) -> list[dict[str, object]]:
        """The routines on the user's week schedule, with each exercise's working-set targets.

        Compact and JSON-ready: this is what the workout agent sees of the plan, and what
        a training proposal may change. Unscheduled routines are left out.
        """

        schedule = list(
            await self.session.execute(
                select(WorkoutScheduleDay.day_of_week, WorkoutPlanEntry)
                .join(WorkoutPlanEntry, WorkoutPlanEntry.id == WorkoutScheduleDay.routine_id)
                .where(WorkoutScheduleDay.owner_id == owner_id)
                .order_by(WorkoutScheduleDay.day_of_week)
            )
        )
        routines: dict[str, dict[str, object]] = {}
        for day, routine in schedule:
            entry = routines.setdefault(
                routine.id,
                {
                    "routine_id": routine.id,
                    "name": routine.name,
                    "revision": routine_revision(routine),
                    "days": [],
                    "exercises": [],
                },
            )
            cast(list[int], entry["days"]).append(day)
        if not routines:
            return []
        rows = await self.session.execute(
            select(WorkoutPlanExercise, Exercise.name)
            .join(Exercise, Exercise.id == WorkoutPlanExercise.exercise_id)
            .where(WorkoutPlanExercise.plan_entry_id.in_(list(routines)))
            .order_by(WorkoutPlanExercise.plan_entry_id, WorkoutPlanExercise.position)
        )
        for planned, name in rows:
            cast(list[dict[str, object]], routines[planned.plan_entry_id]["exercises"]).append(
                {"exercise_id": planned.exercise_id, "name": name, **working_targets(planned.planned_sets)}
            )
        return list(routines.values())

    async def exercise_trends(
        self, owner_id: str, exercise_ids: list[str], start: date_, end: date_, zone: ZoneInfo
    ) -> dict[str, dict[str, object]]:
        """Per exercise: best estimated 1RM and average RPE in the week under review
        (``start``..``end``) against the three weeks before it, and sessions this week."""

        if not exercise_ids:
            return {}
        baseline_start = start - timedelta(days=_TREND_BASELINE_DAYS)
        since, until = utc_bounds(baseline_start, end, zone)
        rows = await self.session.execute(
            select(
                WorkoutSetLog.exercise_id,
                WorkoutSetLog.weight_kg,
                WorkoutSetLog.reps,
                WorkoutSetLog.rpe,
                WorkoutSetLog.kind,
                WorkoutSetLog.session_id,
                WorkoutSession.started_at,
            )
            .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
            .where(
                WorkoutSetLog.owner_id == owner_id,
                WorkoutSetLog.exercise_id.in_(exercise_ids),
                WorkoutSetLog.kind != SetKind.WARMUP,
                WorkoutSession.started_at >= since,
                WorkoutSession.started_at < until,
            )
        )
        buckets: dict[str, dict[str, dict[str, list[object]]]] = {}
        for exercise_id, weight_kg, reps, rpe, kind, session_id, started_at in rows:
            period = "recent" if local_date(started_at, zone) >= start else "prior"
            bucket = buckets.setdefault(exercise_id, {}).setdefault(
                period, {"e1rm": [], "rpe": [], "sessions": []}
            )
            e1rm = estimated_one_rep_max(float(weight_kg), reps)
            if e1rm is not None:
                bucket["e1rm"].append(e1rm)
            # Effort from working sets only: a failure set is RPE 10 by design and would skew it.
            if rpe is not None and kind == SetKind.WORKING:
                bucket["rpe"].append(float(rpe))
            bucket["sessions"].append(session_id)

        def summary(bucket: dict[str, list[object]] | None) -> tuple[float | None, float | None, int]:
            if bucket is None:
                return None, None, 0
            e1rms = cast(list[float], bucket["e1rm"])
            return (
                round(max(e1rms), 1) if e1rms else None,
                average_rpe(cast(list[float], bucket["rpe"])),
                len(set(bucket["sessions"])),
            )

        trends: dict[str, dict[str, object]] = {}
        for exercise_id, periods in buckets.items():
            recent_e1rm, recent_rpe, recent_sessions = summary(periods.get("recent"))
            prior_e1rm, prior_rpe, _ = summary(periods.get("prior"))
            trends[exercise_id] = {
                "recent_best_e1rm_kg": recent_e1rm,
                "prior_best_e1rm_kg": prior_e1rm,
                "recent_avg_rpe": recent_rpe,
                "prior_avg_rpe": prior_rpe,
                "recent_sessions": recent_sessions,
            }
        return trends
