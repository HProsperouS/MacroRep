"""Builds a CoachService and what it depends on, for a request or a background run."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.profile.repository import ProfileRepository
from app.progress.repository import ProgressRepository
from app.workout.repository import WorkoutPlanRepository

from .agents.checkpoint import get_checkpointer
from .agents.provider import get_coach_model
from .apply import ProposalApplier
from .repository import CoachRepository
from .service import CoachService
from .snapshot import WeekSnapshot


def build_coach_service(session: AsyncSession, settings: Settings) -> CoachService:
    profiles = ProfileRepository(session)
    return CoachService(
        session,
        CoachRepository(session),
        profiles,
        WeekSnapshot(ProgressRepository(session), profiles),
        ProposalApplier(session, profiles, WorkoutPlanRepository(session)),
        model=get_coach_model,
        checkpointer=get_checkpointer,
        rate_limits=settings.rate_limits_enabled,
    )
