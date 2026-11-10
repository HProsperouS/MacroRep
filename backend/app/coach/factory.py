"""Builds a CoachService and what it depends on, for a request or a background run."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.profile.repository import ProfileRepository
from app.progress.repository import ProgressRepository
from app.workout.repository import WorkoutPlanRepository

from .agents.checkpoint import get_checkpointer
from .agents.provider import get_coach_model, get_moderator
from .apply import ProposalApplier
from .chat import CoachChat
from .repository import CoachRepository
from .service import CoachService
from .snapshot import WeekSnapshot


def build_coach_service(session: AsyncSession, settings: Settings) -> CoachService:
    profiles = ProfileRepository(session)
    model = get_coach_model
    return CoachService(
        session,
        CoachRepository(session),
        profiles,
        WeekSnapshot(ProgressRepository(session), profiles),
        ProposalApplier(session, profiles, WorkoutPlanRepository(session)),
        chat=CoachChat(session, CoachRepository(session), model, get_moderator),
        model=model,
        checkpointer=get_checkpointer,
        rate_limits=settings.rate_limits_enabled,
    )
