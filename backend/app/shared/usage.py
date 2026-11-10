"""Per-user limits on the paid AI calls, counted in Postgres (plan.md §17).

Each check-in, Coach Chat question and meal photo is a row in ``usage_events``. Counting
rows rather than keeping counts in memory means a restart doesn't reset anyone's allowance,
and every server process enforces the same limit. (The anonymous sign-in limits stay in
memory, keyed by address: see rate_limit.py.)

A count is committed in its own short transaction before the paid call starts, so it's
visible to every process at once. A failure on our side gives it back.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import DateTime, ForeignKey, Index, String, delete, func, insert, select, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import get_session_factory

from .exceptions import TooMany
from .persistence import Base
from .rate_limit import Limit, too_many_message

UsageKind = Literal["check_in", "chat", "photo"]


class UsageEvent(Base):
    """One paid AI call a user made: kept until it falls out of its limit's window."""

    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_events_kind_owner_created", "kind", "owner_id", "created_utc"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


async def spend(kind: UsageKind, owner_id: str, limit: Limit, *, reason: str) -> str:
    """Count one ``kind`` call for ``owner_id``, or refuse with 429 if they're at ``limit``.
    Returns the count's id, for :func:`give_back`.

    Calls made at once for one user queue on an advisory lock, so they can't all count the
    same rows and slip under the limit together. The database's clock is used throughout, so
    every process agrees on the window.
    """

    window = timedelta(seconds=limit.window_seconds)
    async with get_session_factory()() as session, session.begin():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": f"{kind}:{owner_id}"}
        )
        now = (await session.execute(select(func.clock_timestamp()))).scalar_one()
        mine = (UsageEvent.kind == kind) & (UsageEvent.owner_id == owner_id)
        # Rows past the window no longer count: dropped, so the table stays small.
        await session.execute(delete(UsageEvent).where(mine, UsageEvent.created_utc <= now - window))
        count, oldest = (
            await session.execute(select(func.count(), func.min(UsageEvent.created_utc)).where(mine))
        ).one()
        if count >= limit.attempts:
            wait = max(1, math.ceil((oldest + window - now).total_seconds()))
            raise TooMany(too_many_message(wait, reason), retry_after=wait)
        event_id = uuid.uuid4().hex
        await session.execute(
            insert(UsageEvent).values(id=event_id, kind=kind, owner_id=owner_id, created_utc=now)
        )
    return event_id


async def give_back(event_id: str) -> None:
    """Take back a count whose call failed on our side, or never happened."""

    async with get_session_factory()() as session, session.begin():
        await session.execute(delete(UsageEvent).where(UsageEvent.id == event_id))


async def give_back_latest(kind: UsageKind, owner_id: str) -> None:
    """Take back ``owner_id``'s most recent ``kind`` count, for a caller that no longer has its
    id (a check-in's background run, which only one of at a time can be in flight)."""

    async with get_session_factory()() as session, session.begin():
        latest = (
            select(UsageEvent.id)
            .where(UsageEvent.kind == kind, UsageEvent.owner_id == owner_id)
            .order_by(UsageEvent.created_utc.desc())
            .limit(1)
            .scalar_subquery()
        )
        await session.execute(delete(UsageEvent).where(UsageEvent.id == latest))


@asynccontextmanager
async def counted_usage(
    kind: UsageKind, owner_id: str, limit: Limit, *, reason: str, enabled: bool = True
) -> AsyncIterator[None]:
    """Count one call for the block (429 if over ``limit``), given back if the block raises:
    a failure on our side doesn't use up the user's allowance. Does nothing unless ``enabled``."""

    if not enabled:
        yield
        return
    event_id = await spend(kind, owner_id, limit, reason=reason)
    try:
        yield
    except Exception:
        await give_back(event_id)
        raise
