"""Calendar days in the user's own timezone.

Timestamps are stored in UTC, but "today", "this week", and which day a
workout belongs to are the user's local calendar: a 7 a.m. Monday session in
Singapore is 11 p.m. Sunday in UTC and must still count as Monday. Food and
weigh-in dates are already sent as local dates by the browser; this module
covers everything derived from timestamps or the clock.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

DEFAULT_TIMEZONE = "UTC"


@lru_cache(maxsize=1)
def _known_timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def is_known_timezone(name: str) -> bool:
    """True for an IANA name such as ``Asia/Singapore``.

    Checked against the bundled list rather than by loading the name, so a
    value like ``../../etc/passwd`` never reaches the filesystem.
    """

    return name in _known_timezones()


def user_zone(name: str | None) -> ZoneInfo:
    """The zone for a stored name, falling back to UTC for a missing or unknown one."""

    return ZoneInfo(name if name and is_known_timezone(name) else DEFAULT_TIMEZONE)


def local_today(zone: ZoneInfo) -> date:
    return datetime.now(zone).date()


def local_date(moment: datetime, zone: ZoneInfo) -> date:
    """The user's calendar day for a stored timestamp.

    SQLite hands back naive datetimes; everything is stored in UTC, so a
    naive value is read as UTC.
    """

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(zone).date()


def utc_bounds(start: date, end: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """UTC instants spanning local days ``start`` to ``end`` inclusive: ``[from, until)``.

    Filtering timestamps by a range rather than by their date keeps the query
    working the same on SQLite and Postgres, and able to use the timestamp index.
    """

    since = datetime.combine(start, time.min, tzinfo=zone).astimezone(UTC)
    until = datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
    return since, until
