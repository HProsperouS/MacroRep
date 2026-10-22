"""The week's figures a check-in is drafted from, gathered and frozen when it starts."""

from __future__ import annotations

from datetime import date
from typing import cast
from zoneinfo import ZoneInfo

from app.analytics.nutrition import (
    DayStatus,
    average_daily_calories,
    day_statuses,
    logging_adherence_percent,
    logging_completeness,
    target_gap_kcal,
    targets_by_date,
)
from app.analytics.training import average_rpe, completion_percent, planned_sessions
from app.analytics.weight import trend_on_or_before
from app.body.service import trend_by_date
from app.profile.models import ExperienceLevel, Profile
from app.profile.repository import ProfileRepository
from app.profile.service import DEFAULT_TARGETS
from app.progress.repository import ProgressRepository
from app.shared.exceptions import Invalid
from app.shared.timezones import local_date

CHECK_IN_WINDOW_DAYS = 7
MIN_FOOD_LOG_DAYS = 4
MIN_WEIGH_INS = 2


class WeekSnapshot:
    def __init__(self, week_data: ProgressRepository, profiles: ProfileRepository) -> None:
        self.week_data = week_data
        self.profiles = profiles

    async def gather(
        self, owner_id: str, profile: Profile | None, start: date, end: date, zone: ZoneInfo
    ) -> dict[str, object]:
        """Gather the week's metrics, refusing with 422 when there's too little data to judge.

        ``end`` is the user's today, in ``zone``.
        """

        calories_by_date = await self.week_data.daily_calories(owner_id, start, end)
        history = await self.week_data.weigh_ins_up_to(owner_id, end)
        weigh_ins_in_window = [row for row in history if row.log_date >= start]

        missing: list[str] = []
        if len(calories_by_date) < MIN_FOOD_LOG_DAYS:
            missing.append(
                f"log food on at least {MIN_FOOD_LOG_DAYS} of the last {CHECK_IN_WINDOW_DAYS} days "
                f"({len(calories_by_date)} so far)"
            )
        if len(weigh_ins_in_window) < MIN_WEIGH_INS:
            missing.append(f"weigh in at least {MIN_WEIGH_INS} times ({len(weigh_ins_in_window)} so far)")
        if missing:
            raise Invalid(
                f"Not enough data for a check-in yet: {' and '.join(missing)}.",
            )

        trends = trend_by_date(history)
        # A weigh-in from before the window anchors the start; otherwise the
        # window's own first reading does.
        trend_start = trend_on_or_before(trends, start)
        if trend_start is None:
            trend_start = trends[weigh_ins_in_window[0].log_date]
        trend_end = trends[weigh_ins_in_window[-1].log_date]

        # Each day is judged against the target in effect that day; proposals start from today's.
        target_versions = await self.profiles.target_history(owner_id)
        current_targets = target_versions[-1] if target_versions else None
        target_by_date = targets_by_date(
            [(row.effective_date, float(row.calories)) for row in target_versions],
            start,
            end,
            DEFAULT_TARGETS.calories,
        )
        target_calories = round(target_by_date[end])
        # Non-None: the data gate above guarantees at least MIN_FOOD_LOG_DAYS logged days.
        avg_calories = cast(float, average_daily_calories(calories_by_date))
        # Judged from when the user started, as on Progress: days before it weren't missed.
        signed_up = local_date(profile.created_utc, zone) if profile else start
        logged_from = max(start, await self.week_data.logging_started(owner_id, signed_up))
        # `end` is today: still being logged, so it's left out of completeness and the target gap.
        statuses = day_statuses(calories_by_date, logged_from, end, target_by_date, end)
        completeness = logging_completeness(statuses.values())
        finished_logged = [
            (calories_by_date[day], target_by_date[day])
            for day, day_status in statuses.items()
            if day_status in (DayStatus.COMPLETE, DayStatus.PARTIAL)
        ]
        workouts_done = await self.week_data.workouts_done(owner_id, start, end, zone)
        # Nor were plan days before there was a plan: the workout agent holds back progress when
        # completion looks low, so a plan made mid-week mustn't read as missed sessions.
        training_started = await self.week_data.training_started(owner_id, zone)
        workouts_planned = (
            planned_sessions(
                await self.week_data.plan_weekdays(owner_id),
                max(start, training_started),
                end,
                end,
                trained_today=await self.week_data.workouts_done(owner_id, end, end, zone) > 0,
            )
            if training_started
            else 0
        )
        rpe_entries = await self.week_data.rpe_entries(owner_id, start, end, zone)
        routines = await self.week_data.scheduled_routines(owner_id)
        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "avg_calories": round(avg_calories, 1),
            "target_calories": target_calories,
            # The targets version the proposals were made against; applying one checks it is still current.
            "target_version": current_targets.version if current_targets else None,
            "food_log_days": len(calories_by_date),
            "adherence_percent": logging_adherence_percent(
                len(calories_by_date), (end - logged_from).days + 1
            ),
            "complete_days": completeness.complete,
            "partial_days": completeness.partial,
            "missing_days": completeness.missing,
            "target_gap_kcal": target_gap_kcal(finished_logged),
            "weigh_ins": len(weigh_ins_in_window),
            "weight_change_kg": round(trend_end - trend_start, 2),
            "goal_rate_kg_per_week": float(profile.weekly_rate_kg) if profile else 0.0,
            "workouts_done": workouts_done,
            "workouts_planned": workouts_planned,
            "completion_percent": completion_percent(workouts_done, workouts_planned),
            "avg_rpe": average_rpe(rpe for _, rpe in rpe_entries),
            # What the workout agent may adjust, and how each exercise has been going.
            "routines": routines,
            "exercise_trends": await self.week_data.exercise_trends(
                owner_id,
                sorted(
                    {
                        cast(str, e["exercise_id"])
                        for r in routines
                        for e in cast(list[dict[str, object]], r["exercises"])
                    }
                ),
                start,
                end,
                zone,
            ),
            # A profile not made yet would start as a beginner.
            "experience_level": (profile.experience_level if profile else ExperienceLevel.BEGINNER).value,
            "goal": profile.goal.value if profile else "maintain",
        }
