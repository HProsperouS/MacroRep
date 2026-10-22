"""Which days count, shared by Progress, Home and the check-in so they judge a week alike."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from app.analytics.training import planned_sessions
from app.profile.models import Profile
from app.shared.timezones import local_date, local_today

from .repository import ProgressRepository


async def logging_counted_from(
    week_data: ProgressRepository, owner_id: str, profile: Profile | None, start: date, zone: ZoneInfo
) -> date:
    """The first day from ``start`` that food logging is judged on. Days before the user signed up
    (or first logged, if they backfilled earlier) weren't missed. With no profile yet, they sign up today."""

    signed_up = local_date(profile.created_utc, zone) if profile else local_today(zone)
    return max(start, await week_data.logging_started(owner_id, signed_up))


async def workouts_planned(
    week_data: ProgressRepository, owner_id: str, start: date, end: date, today: date, zone: ZoneInfo
) -> int:
    """Workouts the plan had due from ``start`` to ``end``. Plan days before the user first had a
    plan weren't missed, and with no plan none were."""

    training_started = await week_data.training_started(owner_id, zone)
    if training_started is None:
        return 0
    return planned_sessions(
        await week_data.plan_weekdays(owner_id),
        max(start, training_started),
        end,
        today,
        # Today only matters while the range reaches it.
        trained_today=end >= today and await week_data.workouts_done(owner_id, today, today, zone) > 0,
    )
