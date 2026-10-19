"""Background generation of a check-in's proposals.

``POST /check-ins`` answers as soon as the check-in is recorded as RUNNING; the
proposals are drafted afterwards, here, in a session of their own (the request's
session is closed by then). The client polls the check-in until it leaves RUNNING.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select

from app.core.database import get_session_factory
from app.profile.repository import ProfileRepository
from app.progress.repository import ProgressRepository

from .models import CheckIn, CheckInStatus
from .repository import CoachRepository
from .service import CoachService

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


async def resume_interrupted_check_ins() -> None:
    """At startup, pick up check-ins left RUNNING by a restart. Each continues from
    its last checkpoint (on Postgres), so finished agent steps aren't run again; one
    that is too old is marked failed by ``generate``'s stale check instead."""

    async with get_session_factory()() as session:
        running = list(
            await session.scalars(select(CheckIn.id).where(CheckIn.status == CheckInStatus.RUNNING))
        )
    for check_in_id in running:
        task = asyncio.create_task(generate_check_in(check_in_id))
        _running.add(task)
        task.add_done_callback(_running.discard)


async def stop_running_check_ins() -> None:
    """At shutdown, before the checkpointer closes: stop every run in progress. A cancelled
    run stays RUNNING, with its finished steps checkpointed, and is resumed at the next start."""

    tasks = [task for task in _running if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
