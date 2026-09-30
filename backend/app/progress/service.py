"""Progress dashboard aggregation.

Composes food, workout, body, and coach data into the read-only shapes the
frontend charts render. Nothing here is persisted; it is recomputed per
request from the owning domains' own records.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta

from app.analytics.nutrition import (
    DayStatus,
    average_daily_calories,
    day_statuses,
    estimate_expenditure,
    logging_adherence_percent,
    logging_completeness,
    target_adherence_percent,
    target_gap_kcal,
)
from app.analytics.training import (
    average_rpe_by_week,
    completion_percent,
    percent_change,
    planned_sessions,
    week_start,
)
from app.analytics.weight import rate_per_week
from app.body.service import trend_by_date
from app.coach.models import ProposalStatus
from app.coach.repository import CoachRepository
from app.identity.dependencies import ActorContext
from app.profile.repository import ProfileRepository
from app.shared.timezones import local_date, local_today, user_zone

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
        profile = await self.profiles.get(actor.actor_id)
        zone = user_zone(profile.timezone if profile else None)
        today = local_today(zone)
        history = await self.repository.weigh_ins_up_to(actor.actor_id, today)
        earliest = history[0].log_date if history else None
        date_from, date_to = self._resolve_range(progress_range, earliest, today)
        days_in_range = max((date_to - date_from).days + 1, 1)

        trends = trend_by_date([row for row in history if row.log_date <= date_to])
        scale_by_date = {row.log_date: float(row.weight_kg) for row in history}

        points: list[WeightPoint] = []
        last_trend = 0.0
        cursor = date_from
        while cursor <= date_to:
            if cursor in trends:
                last_trend = trends[cursor]
            points.append(WeightPoint(date=cursor, scale_kg=scale_by_date.get(cursor), trend_kg=last_trend))
            cursor += timedelta(days=1)

        trend_at_start = points[0].trend_kg if points else 0.0
        trend_at_end = points[-1].trend_kg if points else 0.0
        change_kg = round(trend_at_end - trend_at_start, 2)
        rate_per_week_kg = rate_per_week(change_kg, days_in_range)

        goal_rate = float(profile.weekly_rate_kg) if profile else 0.0
        target_calories = profile.target_calories if profile else 2000

        calories_by_date = await self.repository.daily_calories(actor.actor_id, date_from, date_to)
        status_by_date = day_statuses(calories_by_date, date_from, date_to, target_calories, today)
        completeness = logging_completeness(status_by_date.values())
        logged_days = completeness.complete + completeness.partial
        adherence_percent = logging_adherence_percent(logged_days, sum(completeness))
        finished_logged = _finished_logged_calories(calories_by_date, status_by_date)
        logging = LoggingSummary(
            complete_days=completeness.complete,
            partial_days=completeness.partial,
            missing_days=completeness.missing,
            target_adherence_percent=target_adherence_percent(finished_logged, target_calories),
            target_gap_kcal=target_gap_kcal(finished_logged, target_calories),
        )
        avg_calories = average_daily_calories(calories_by_date)
        expenditure_kcal_per_day = estimate_expenditure(
            avg_calories if avg_calories is not None else target_calories, change_kg, days_in_range
        )

        workouts_done = await self.repository.workouts_done(actor.actor_id, date_from, date_to, zone)
        trained_today = await self.repository.workouts_done(actor.actor_id, today, today, zone) > 0
        workouts_planned = planned_sessions(
            await self.repository.plan_weekdays(actor.actor_id), date_from, date_to, today, trained_today
        )

        weekly_volume = await self.repository.weekly_volume(actor.actor_id, date_from, date_to, zone)
        rpe_in_range = await self.repository.rpe_entries(actor.actor_id, date_from, date_to, zone)
        weekly_rpe = average_rpe_by_week(rpe_in_range)
        weeks = [
            VolumeWeek(week_start=week, tonnes=round(kg / 1000, 2), avg_rpe=weekly_rpe.get(week))
            for week, kg in sorted(weekly_volume.items())
        ]
        average_tonnes = round(sum(w.tonnes for w in weeks) / len(weeks), 2) if weeks else 0.0

        # Queried on their own rather than read from `weekly_volume`, so the
        # comparison doesn't depend on the selected range covering both weeks.
        last_week = week_start(today) - timedelta(days=7)
        week_before = last_week - timedelta(days=7)
        last_week_end = last_week + timedelta(days=6)
        recent_volume = await self.repository.weekly_volume(actor.actor_id, week_before, last_week_end, zone)
        last_week_kg = recent_volume.get(last_week, 0.0)
        change_percent = percent_change(recent_volume.get(week_before, 0.0), last_week_kg)
        # Unlike volume (a total, which a half-finished week understates), RPE is an
        # average, so the current week is meaningful as soon as one set has an RPE.
        this_week = week_start(today)
        recent_rpe = average_rpe_by_week(
            await self.repository.rpe_entries(actor.actor_id, last_week, today, zone)
        )
        this_week_rpe = recent_rpe.get(this_week)
        last_week_rpe = recent_rpe.get(last_week)
        rpe = RpeSummary(
            this_week_avg=this_week_rpe,
            change=(
                round(this_week_rpe - last_week_rpe, 1)
                if this_week_rpe is not None and last_week_rpe is not None
                else None
            ),
        )

        lifts = await self.repository.strength_lifts(actor.actor_id, date_from, date_to, zone)
        strength = [
            StrengthLift(
                exercise=name, estimated1_rm_kg=round(current, 1), change_kg=round(current - before, 1)
            )
            for name, (before, current) in lifts.items()
        ]

        check_ins_rows = await self.repository.check_ins_in_range(actor.actor_id, date_from, date_to, zone)
        proposals_by_check_in = await self.coach.list_proposals_for_check_ins(
            [check_in.id for check_in in check_ins_rows]
        )
        check_ins: list[CheckInHistoryItem] = []
        for check_in in check_ins_rows:
            statuses = {p.status for p in proposals_by_check_in[check_in.id]}
            if ProposalStatus.APPLIED in statuses:
                outcome = "applied"
            elif ProposalStatus.EDITED in statuses:
                outcome = "edited"
            elif ProposalStatus.REJECTED in statuses:
                outcome = "rejected"
            else:
                outcome = "no-changes"
            check_ins.append(
                CheckInHistoryItem(
                    id=check_in.id,
                    week_label=check_in.week_label,
                    date=local_date(check_in.created_utc, zone),
                    summary=check_in.summary,
                    outcome=outcome,
                )
            )

        return ProgressResponse(
            range=progress_range,
            **{"from": date_from, "to": date_to},
            weight=WeightSummary(
                points=points,
                current_trend_kg=trend_at_end,
                change_kg=change_kg,
                rate_per_week_kg=rate_per_week_kg,
                goal_rate_per_week_kg=goal_rate,
            ),
            expenditure_kcal_per_day=expenditure_kcal_per_day,
            adherence_percent=adherence_percent,
            logging=logging,
            workouts=WorkoutsSummary(
                done=workouts_done,
                planned=workouts_planned,
                completion_percent=completion_percent(workouts_done, workouts_planned),
            ),
            volume=VolumeSummary(
                weeks=weeks,
                average_tonnes=average_tonnes,
                last_week_tonnes=round(last_week_kg / 1000, 2),
                change_percent=change_percent,
            ),
            rpe=rpe,
            strength=strength,
            check_ins=check_ins,
        )

    async def get_daily_calories(self, actor: ActorContext, days: int) -> DailyCaloriesResponse:
        profile = await self.profiles.get(actor.actor_id)
        today = local_today(user_zone(profile.timezone if profile else None))
        start = today - timedelta(days=days - 1)
        calories_by_date = await self.repository.daily_calories(actor.actor_id, start, today)
        target_calories = profile.target_calories if profile else 2000
        status_by_date = day_statuses(calories_by_date, start, today, target_calories, today)
        finished_logged = _finished_logged_calories(calories_by_date, status_by_date)
        return DailyCaloriesResponse(
            days=[
                DailyCalories(date=day, calories=calories_by_date.get(day, 0), status=status)
                for day, status in status_by_date.items()
            ],
            target_calories=target_calories,
            target_gap_kcal=target_gap_kcal(finished_logged, target_calories),
        )


def _finished_logged_calories(
    calories_by_date: Mapping[date, int], statuses: Mapping[date, DayStatus]
) -> list[int]:
    """Intake of each logged day that's over: today is left out until it ends."""

    return [
        calories_by_date[day]
        for day, status in statuses.items()
        if status in (DayStatus.COMPLETE, DayStatus.PARTIAL)
    ]
