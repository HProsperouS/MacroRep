"""Progress dashboard aggregation.

Composes food, workout, body, and coach data into the read-only shapes the
frontend charts render. Nothing here is persisted; it is recomputed per
request from the owning domains' own records.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from app.analytics.nutrition import (
    DayStatus,
    day_statuses,
    logging_adherence_percent,
    logging_completeness,
    target_adherence_percent,
    target_gap_kcal,
    targets_by_date,
)
from app.analytics.training import average_rpe_by_week, completion_percent, percent_change, week_start
from app.analytics.weight import rate_per_week
from app.body.models import WeighIn
from app.body.service import trend_by_date
from app.coach.models import ProposalStatus
from app.coach.repository import CoachRepository
from app.identity.dependencies import ActorContext
from app.profile.models import Profile
from app.profile.repository import ProfileRepository
from app.profile.service import DEFAULT_TARGETS, zone_of
from app.shared.timezones import local_date, local_today

from .days import logging_counted_from, workouts_planned
from .repository import ProgressRepository
from .schemas import (
    CheckInHistoryItem,
    DailyCalories,
    DailyCaloriesResponse,
    LoggingSummary,
    ProgressRange,
    ProgressResponse,
    RpeSummary,
    StrengthLift,
    VolumeSummary,
    VolumeWeek,
    WeightPoint,
    WeightSummary,
    WorkoutsSummary,
)

_RANGE_DAYS: dict[str, int] = {"1M": 30, "3M": 90, "6M": 182, "1Y": 365}
# Weigh-ins must cover this many days for a weekly rate. (Stricter than a check-in, which
# needs two weigh-ins within its 7 days: it reads the change, not a rate to judge pace by.)
RATE_NEEDS_DAYS = 7


class ProgressService:
    def __init__(
        self,
        repository: ProgressRepository,
        profiles: ProfileRepository,
        coach: CoachRepository,
    ) -> None:
        self.repository = repository
        self.profiles = profiles
        self.coach = coach

    def _resolve_range(
        self, progress_range: ProgressRange, earliest: date | None, today: date
    ) -> tuple[date, date]:
        if progress_range == "All":
            return (earliest or today, today)
        days = _RANGE_DAYS[progress_range]
        return (today - timedelta(days=days - 1), today)

    async def get_progress(self, actor: ActorContext, progress_range: ProgressRange) -> ProgressResponse:
        owner_id = actor.actor_id
        profile = await self.profiles.get(owner_id)
        zone = zone_of(profile)
        today = local_today(zone)
        history = await self.repository.weigh_ins_up_to(owner_id, today)
        earliest = history[0].log_date if history else None
        date_from, date_to = self._resolve_range(progress_range, earliest, today)
        adherence_percent, logging = await self._logging(owner_id, profile, date_from, date_to, today, zone)
        return ProgressResponse(
            range=progress_range,
            **{"from": date_from, "to": date_to},
            weight=self._weight(history, date_from, date_to, profile),
            adherence_percent=adherence_percent,
            logging=logging,
            workouts=await self._workouts(owner_id, date_from, date_to, today, zone),
            volume=await self._volume(owner_id, date_from, date_to, today, zone),
            rpe=await self._rpe(owner_id, today, zone),
            strength=await self._strength(owner_id, date_from, date_to, zone),
            check_ins=await self._check_ins(owner_id, date_from, date_to, zone),
        )

    def _weight(
        self, history: list[WeighIn], date_from: date, date_to: date, profile: Profile | None
    ) -> WeightSummary:
        trends = trend_by_date([row for row in history if row.log_date <= date_to])
        scale_by_date = {row.log_date: float(row.weight_kg) for row in history}

        points: list[WeightPoint] = []
        # The trend carries in from the last weigh-in before the range, if any. Before the
        # first weigh-in ever there's none: a day with no weight isn't a weight of 0.
        before = [row.log_date for row in history if row.log_date < date_from]
        last_trend: float | None = trends[before[-1]] if before else None
        cursor = date_from
        while cursor <= date_to:
            if cursor in trends:
                last_trend = trends[cursor]
            points.append(WeightPoint(date=cursor, scale_kg=scale_by_date.get(cursor), trend_kg=last_trend))
            cursor += timedelta(days=1)

        # The change is measured over the days that have a trend, from the first of them.
        trended = [(point.date, point.trend_kg) for point in points if point.trend_kg is not None]
        change_kg = round(trended[-1][1] - trended[0][1], 2) if trended else 0.0
        trend_days = (
            (trended[-1][0] - trended[0][0]).days + 1 if trended else max((date_to - date_from).days + 1, 1)
        )
        # A weekly rate needs the weigh-ins it rests on (the one carried in, and those in range)
        # to cover a week: one gives no change, and two a day or two apart turn day-to-day
        # swings (water, food) into a rate several times too big.
        weighed = before[-1:] + [row.log_date for row in history if date_from <= row.log_date <= date_to]
        weighed_over_a_week = len(weighed) >= 2 and (weighed[-1] - weighed[0]).days + 1 >= RATE_NEEDS_DAYS
        return WeightSummary(
            points=points,
            current_trend_kg=trended[-1][1] if trended else None,
            change_kg=change_kg,
            rate_per_week_kg=rate_per_week(change_kg, trend_days) if weighed_over_a_week else None,
            goal_rate_per_week_kg=float(profile.weekly_rate_kg) if profile else 0.0,
        )

    async def _logging(
        self,
        owner_id: str,
        profile: Profile | None,
        date_from: date,
        date_to: date,
        today: date,
        zone: ZoneInfo,
    ) -> tuple[float | None, LoggingSummary]:
        """How fully food was logged in the range, and how close it came to the targets."""

        target_by_date = targets_by_date(
            await self.profiles.calorie_target_versions(owner_id),
            date_from,
            date_to,
            DEFAULT_TARGETS.calories,
        )
        counted_from = await logging_counted_from(self.repository, owner_id, profile, date_from, zone)
        calories_by_date = await self.repository.daily_calories(owner_id, counted_from, date_to)
        status_by_date = day_statuses(calories_by_date, counted_from, date_to, target_by_date, today)
        completeness = logging_completeness(status_by_date.values())
        logged_days = completeness.complete + completeness.partial
        finished_days = sum(completeness)
        adherence_percent = logging_adherence_percent(logged_days, finished_days) if finished_days else None
        finished_logged = _finished_logged_days(calories_by_date, status_by_date, target_by_date)
        return adherence_percent, LoggingSummary(
            complete_days=completeness.complete,
            partial_days=completeness.partial,
            target_adherence_percent=target_adherence_percent(finished_logged),
            target_gap_kcal=target_gap_kcal(finished_logged),
        )

    async def _workouts(
        self, owner_id: str, date_from: date, date_to: date, today: date, zone: ZoneInfo
    ) -> WorkoutsSummary:
        done = await self.repository.workouts_done(owner_id, date_from, date_to, zone)
        planned = await workouts_planned(self.repository, owner_id, date_from, date_to, today, zone)
        return WorkoutsSummary(
            done=done, planned=planned, completion_percent=completion_percent(done, planned)
        )

    async def _volume(
        self, owner_id: str, date_from: date, date_to: date, today: date, zone: ZoneInfo
    ) -> VolumeSummary:
        weekly_volume = await self.repository.weekly_volume(owner_id, date_from, date_to, zone)
        weekly_rpe = average_rpe_by_week(
            await self.repository.rpe_entries(owner_id, date_from, date_to, zone)
        )
        weeks = [
            VolumeWeek(week_start=week, tonnes=round(kg / 1000, 2), avg_rpe=weekly_rpe.get(week))
            for week, kg in sorted(weekly_volume.items())
        ]
        # Queried on their own rather than read from `weekly_volume`, so the
        # comparison doesn't depend on the selected range covering both weeks.
        last_week = week_start(today) - timedelta(days=7)
        week_before = last_week - timedelta(days=7)
        recent_volume = await self.repository.weekly_volume(
            owner_id, week_before, last_week + timedelta(days=6), zone
        )
        last_week_kg = recent_volume.get(last_week, 0.0)
        return VolumeSummary(
            weeks=weeks,
            average_tonnes=round(sum(w.tonnes for w in weeks) / len(weeks), 2) if weeks else 0.0,
            last_week_tonnes=round(last_week_kg / 1000, 2),
            change_percent=percent_change(recent_volume.get(week_before, 0.0), last_week_kg),
        )

    async def _rpe(self, owner_id: str, today: date, zone: ZoneInfo) -> RpeSummary:
        # Unlike volume (a total, which a half-finished week understates), RPE is an
        # average, so the current week is meaningful as soon as one set has an RPE.
        this_week = week_start(today)
        last_week = this_week - timedelta(days=7)
        recent_rpe = average_rpe_by_week(await self.repository.rpe_entries(owner_id, last_week, today, zone))
        this_week_rpe = recent_rpe.get(this_week)
        last_week_rpe = recent_rpe.get(last_week)
        return RpeSummary(
            this_week_avg=this_week_rpe,
            change=(
                round(this_week_rpe - last_week_rpe, 1)
                if this_week_rpe is not None and last_week_rpe is not None
                else None
            ),
        )

    async def _strength(
        self, owner_id: str, date_from: date, date_to: date, zone: ZoneInfo
    ) -> list[StrengthLift]:
        lifts = await self.repository.strength_lifts(owner_id, date_from, date_to, zone)
        return [
            StrengthLift(
                exercise=name, estimated1_rm_kg=round(current, 1), change_kg=round(current - before, 1)
            )
            for name, (before, current) in lifts.items()
        ]

    async def _check_ins(
        self, owner_id: str, date_from: date, date_to: date, zone: ZoneInfo
    ) -> list[CheckInHistoryItem]:
        rows = await self.repository.check_ins_in_range(owner_id, date_from, date_to, zone)
        proposals_by_check_in = await self.coach.list_proposals_for_check_ins([row.id for row in rows])
        return [
            CheckInHistoryItem(
                id=check_in.id,
                week_label=check_in.week_label,
                date=local_date(check_in.created_utc, zone),
                summary=check_in.summary,
                outcome=_outcome({p.status for p in proposals_by_check_in[check_in.id]}),
            )
            for check_in in rows
        ]

    async def get_daily_calories(self, actor: ActorContext, days: int) -> DailyCaloriesResponse:
        profile = await self.profiles.get(actor.actor_id)
        zone = zone_of(profile)
        today = local_today(zone)
        # Days before the user started weren't missed, so they aren't shown (as on Progress).
        start = await logging_counted_from(
            self.repository, actor.actor_id, profile, today - timedelta(days=days - 1), zone
        )
        calories_by_date = await self.repository.daily_calories(actor.actor_id, start, today)
        target_by_date = targets_by_date(
            await self.profiles.calorie_target_versions(actor.actor_id),
            start,
            today,
            DEFAULT_TARGETS.calories,
        )
        status_by_date = day_statuses(calories_by_date, start, today, target_by_date, today)
        finished_logged = _finished_logged_days(calories_by_date, status_by_date, target_by_date)
        return DailyCaloriesResponse(
            days=[
                DailyCalories(
                    date=day,
                    calories=calories_by_date.get(day, 0),
                    status=status,
                    target_calories=round(target_by_date[day]),
                )
                for day, status in status_by_date.items()
            ],
            target_calories=round(target_by_date[today]),
            target_gap_kcal=target_gap_kcal(finished_logged),
        )


def _finished_logged_days(
    calories_by_date: Mapping[date, int],
    statuses: Mapping[date, DayStatus],
    target_by_date: Mapping[date, float],
) -> list[tuple[float, float]]:
    """(intake, that day's target) of each logged day that's over: today is left out until it ends."""

    return [
        (calories_by_date[day], target_by_date[day])
        for day, status in statuses.items()
        if status in (DayStatus.COMPLETE, DayStatus.PARTIAL)
    ]


def _outcome(statuses: set[ProposalStatus]) -> str:
    """A check-in's outcome on the Progress history, from what became of its proposals."""

    if ProposalStatus.APPLIED in statuses:
        return "applied"
    if ProposalStatus.EDITED in statuses:
        return "edited"
    if ProposalStatus.REJECTED in statuses:
        return "rejected"
    return "no-changes"
