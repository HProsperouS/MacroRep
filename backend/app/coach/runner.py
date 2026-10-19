"""Background generation of a check-in's proposals.

``POST /check-ins`` answers as soon as the check-in is recorded as RUNNING; the
proposals are drafted afterwards, here, in a session of their own (the request's
session is closed by then). The client polls the check-in until it leaves RUNNING.
"""

from __future__ import annotations

from app.core.database import get_session_factory
from app.profile.repository import ProfileRepository
from app.progress.repository import ProgressRepository

from .repository import CoachRepository
from .service import CoachService


async def generate_check_in(check_in_id: str) -> None:
    async with get_session_factory()() as session:
        service = CoachService(
            session, CoachRepository(session), ProgressRepository(session), ProfileRepository(session)
        )
        await service.generate(check_in_id)
