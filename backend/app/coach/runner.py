"""Background generation of a check-in's proposals.

``POST /check-ins`` answers as soon as the check-in is recorded as RUNNING; the
proposals are drafted afterwards, here, in a session of their own (the request's
session is closed by then). The client polls the check-in until it leaves RUNNING.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.database import get_session_factory
from app.profile.repository import ProfileRepository
from app.progress.repository import ProgressRepository

from .models import CheckIn, CheckInStatus
from .repository import CoachRepository
from .service import RUN_TIMEOUT_SECONDS, CoachService

# Every generation running in this process: the router's background runs and the
# resumed ones. Strong references also keep a resumed task from being garbage-collected.
_running: set[asyncio.Task[Any]] = set()


async def generate_check_in(check_in_id: str) -> None:
    task = asyncio.current_task()
    if task is not None:
        _running.add(task)
    try:
        async with get_session_factory()() as session:
            service = CoachService(
                session, CoachRepository(session), ProgressRepository(session), ProfileRepository(session)
            )
            await service.generate(check_in_id)
    finally:
        if task is not None:
            _running.discard(task)


# Margin after a run's own time limit before another task takes it over.
_TAKEOVER_MARGIN_SECONDS = 10


async def resume_interrupted_check_ins() -> None:
    """At startup, pick up check-ins left RUNNING by a restart. Each continues from
    its last checkpoint (on Postgres), so finished agent steps aren't run again; one
    that is too old is marked failed by ``generate``'s stale check instead.

    A RUNNING check-in may instead belong to another task that is alive and still working
    on it (during a rolling deploy, or when scaling out). A run can't outlast
    ``RUN_TIMEOUT_SECONDS``, so this waits until that has passed since the check-in
    started: by then a live owner has finished it or marked it failed, and ``generate``
    sees it's no longer RUNNING. Only a run whose owner died is still RUNNING to resume.
    """

    async with get_session_factory()() as session:
        running = list(
            await session.execute(
                select(CheckIn.id, CheckIn.created_utc).where(CheckIn.status == CheckInStatus.RUNNING)
            )
        )
    now = datetime.now(UTC)
    for check_in_id, created in running:
        started = created if created.tzinfo else created.replace(tzinfo=UTC)
        owner_done_by = started + timedelta(seconds=RUN_TIMEOUT_SECONDS + _TAKEOVER_MARGIN_SECONDS)
        task = asyncio.create_task(_resume_after(check_in_id, (owner_done_by - now).total_seconds()))
        _running.add(task)
        task.add_done_callback(_running.discard)


async def _resume_after(check_in_id: str, delay_seconds: float) -> None:
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)
    await generate_check_in(check_in_id)


async def stop_running_check_ins() -> None:
    """At shutdown, before the checkpointer closes: stop every run in progress. A cancelled
    run stays RUNNING, with its finished steps checkpointed, and is resumed at the next start."""

    tasks = [task for task in _running if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
