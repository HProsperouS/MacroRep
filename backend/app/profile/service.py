"""Profile read/update rules, including first-touch provisioning."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext
from app.identity.repository import UserRepository

from .models import ExperienceLevel, Goal, Profile
from .repository import ProfileRepository
from .schemas import DailyTargets, ProfileRead, UpdateProfileInput

_DEFAULT_TARGETS = DailyTargets(calories=2200, protein=150, carbs=230, fat=70)


class ProfileService:
    def __init__(self, session: AsyncSession, repository: ProfileRepository, users: UserRepository) -> None:
        self.session = session
        self.repository = repository
        self.users = users

    async def _get_or_create(self, actor: ActorContext) -> Profile:
        profile = await self.repository.get(actor.actor_id)
        if profile is not None:
            return profile
        profile = Profile(
            user_id=actor.actor_id,
            name=actor.display_name,
            height_cm=170,
            goal=Goal.MAINTAIN,
            weekly_rate_kg=0,
            training_days_per_week=3,
            experience_level=ExperienceLevel.BEGINNER,
            equipment=[],
            target_calories=_DEFAULT_TARGETS.calories,
            target_protein_g=_DEFAULT_TARGETS.protein,
            target_carbs_g=_DEFAULT_TARGETS.carbs,
            target_fat_g=_DEFAULT_TARGETS.fat,
        )
        await self.repository.add(profile)
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def _to_read(self, profile: Profile, actor: ActorContext) -> ProfileRead:
        user = await self.users.get(actor.actor_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        return ProfileRead(
            name=profile.name,
            email=user.email,
            height_cm=float(profile.height_cm),
            goal=profile.goal,
            weekly_rate_kg=float(profile.weekly_rate_kg),
            training_days_per_week=profile.training_days_per_week,
            experience_level=profile.experience_level,
            equipment=list(profile.equipment),
        )

    async def get(self, actor: ActorContext) -> ProfileRead:
        profile = await self._get_or_create(actor)
        return await self._to_read(profile, actor)

    async def update(self, payload: UpdateProfileInput, actor: ActorContext) -> ProfileRead:
        profile = await self._get_or_create(actor)
        profile.name = payload.name
        profile.height_cm = payload.height_cm
        profile.goal = payload.goal
        profile.weekly_rate_kg = payload.weekly_rate_kg
        profile.training_days_per_week = payload.training_days_per_week
        profile.experience_level = payload.experience_level
        profile.equipment = payload.equipment
        profile.touch()
        await self.session.commit()
        await self.session.refresh(profile)
        return await self._to_read(profile, actor)

    async def get_targets(self, actor: ActorContext) -> DailyTargets:
        profile = await self._get_or_create(actor)
        return DailyTargets(
            calories=profile.target_calories,
            protein=float(profile.target_protein_g),
            carbs=float(profile.target_carbs_g),
            fat=float(profile.target_fat_g),
        )

    async def update_targets(self, payload: DailyTargets, actor: ActorContext) -> DailyTargets:
        profile = await self._get_or_create(actor)
        profile.target_calories = payload.calories
        profile.target_protein_g = payload.protein
        profile.target_carbs_g = payload.carbs
        profile.target_fat_g = payload.fat
        profile.touch()
        await self.session.commit()
        return payload
