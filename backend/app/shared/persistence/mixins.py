"""Reusable timestamp columns.

MacroRep records are single-owner personal data (a user's own food log,
workouts, weigh-ins), not shared organizational records accessed by multiple
staff, so the CRM-grade "who changed what" actor audit trail is unneeded
complexity here. Plain creation/update timestamps are enough; rows a user
deletes (e.g. a food-log entry) are hard-deleted by their owner-scoped
repository rather than soft-deleted.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


def utc_now() -> datetime:
    """Return an aware UTC datetime suitable for database persistence."""

    return datetime.now(UTC)


class TimestampMixin:
    """Creation and last-update timestamps for an owner-scoped record."""

    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def touch(self) -> None:
        self.updated_utc = utc_now()
