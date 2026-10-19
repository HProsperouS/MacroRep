"""Profile read/update rules, including first-touch provisioning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext
from app.identity.repository import UserRepository
from app.shared.timezones import DEFAULT_TIMEZONE, local_today, user_zone

from .models import ExperienceLevel, Goal, NutritionTarget, Profile, TargetSource
from .repository import ProfileRepository
from .schemas import DailyTargets, ProfileRead, TargetVersionRead, TimezoneInput, UpdateProfileInput

# A profile this young that sets its timezone is a new sign-up, not a user who travelled.
_NEW_ACCOUNT = timedelta(days=1)
# Given to a new profile, and used to judge days for a user who has no targets yet.
DEFAULT_TARGETS = DailyTargets(calories=2200, protein=150, carbs=230, fat=70)


def _one_decimal(value: float) -> float:
    """Round half up to one decimal, as the Numeric(6, 1) columns store it; round() takes 150.25 down."""

    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def to_daily_targets(target: NutritionTarget) -> DailyTargets:
    return DailyTargets(
        calories=target.calories,
        protein=float(target.protein_g),
        carbs=float(target.carbs_g),
        fat=float(target.fat_g),
    )


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
        )
        await self.repository.add(profile)
        await self._add_targets(profile, None, DEFAULT_TARGETS, TargetSource.INITIAL)
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
            timezone=profile.timezone,
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

    async def set_timezone(self, payload: TimezoneInput, actor: ActorContext) -> ProfileRead:
        profile = await self._get_or_create(actor)
        if profile.timezone != payload.timezone:
            first_sync = profile.timezone == DEFAULT_TIMEZONE
            profile.timezone = payload.timezone
            profile.touch()
            if first_sync:
                await self._redate_starting_targets(profile)
            await self.session.commit()
            await self.session.refresh(profile)
        return await self._to_read(profile, actor)

    async def _redate_starting_targets(self, profile: Profile) -> None:
        """A new profile is created before the browser has sent its timezone, so its starting
        targets were dated by UTC: a day off around midnight. When the real zone arrives for a
        new account that has changed nothing yet, date them by the user's own day instead,
        or a target set on sign-up day would look like it came a day after the starting one."""

        history = await self.repository.target_history(profile.user_id)
        if len(history) != 1 or history[0].source != TargetSource.INITIAL:
            return
        created = (
            profile.created_utc if profile.created_utc.tzinfo else profile.created_utc.replace(tzinfo=UTC)
        )
        if datetime.now(UTC) - created > _NEW_ACCOUNT:
            return
        history[0].effective_date = local_today(user_zone(profile.timezone))

    async def _add_targets(
        self, profile: Profile, previous: NutritionTarget | None, targets: DailyTargets, source: TargetSource
    ) -> None:
        await self.repository.add_target_version(
            profile.user_id,
            previous=previous,
            calories=targets.calories,
            protein=targets.protein,
            carbs=targets.carbs,
            fat=targets.fat,
            effective_date=local_today(user_zone(profile.timezone)),
            source=source,
        )

    async def get_targets(self, actor: ActorContext) -> DailyTargets:
        profile = await self._get_or_create(actor)
        current = await self.repository.current_targets(profile.user_id)
        return to_daily_targets(current) if current else DEFAULT_TARGETS

    async def update_targets(self, payload: DailyTargets, actor: ActorContext) -> DailyTargets:
        """Record the targets as a new version from today; saving unchanged targets adds nothing."""

        profile = await self._get_or_create(actor)
        current = await self.repository.current_targets(profile.user_id)
        # Macros are stored to one decimal, so compare at that precision; otherwise 150.25
        # (stored as 150.3) would never match and every resave would add a version.
        stored = DailyTargets(
            calories=payload.calories,
            protein=_one_decimal(payload.protein),
            carbs=_one_decimal(payload.carbs),
            fat=_one_decimal(payload.fat),
        )
        if current is not None and to_daily_targets(current) == stored:
            return stored
        try:
            await self._add_targets(profile, current, stored, TargetSource.MANUAL)
            await self.session.commit()
        except IntegrityError:
            # Another change to the targets was saved at the same moment and took this version number.
            await self.session.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Your targets were just changed elsewhere, please retry"
            ) from None
        return stored

    async def target_history(self, actor: ActorContext) -> list[TargetVersionRead]:
        """Every version of the targets, newest first."""

        profile = await self._get_or_create(actor)
        return [
            TargetVersionRead(
                **to_daily_targets(row).model_dump(),
                version=row.version,
                effective_date=row.effective_date,
                source=row.source,
                # SQLite hands back naive datetimes; everything is stored in UTC.
                changed_at=row.created_utc if row.created_utc.tzinfo else row.created_utc.replace(tzinfo=UTC),
            )
            for row in reversed(await self.repository.target_history(profile.user_id))
        ]
