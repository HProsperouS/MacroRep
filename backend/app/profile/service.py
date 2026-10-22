"""Profile read/update rules, including first-touch provisioning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.energy import ActivityLevel, Sex, age_on, estimate_targets
from app.body.repository import WeighInRepository
from app.identity.dependencies import ActorContext
from app.identity.repository import UserRepository
from app.shared.persistence.mixins import utc_now
from app.shared.timezones import DEFAULT_TIMEZONE, local_today, user_zone
from app.shared.validation import (
    MAX_TARGET_CALORIES,
    MAX_TARGET_CARBS_G,
    MAX_TARGET_HISTORY,
    MAX_TARGET_PROTEIN_G,
    MIN_TARGET_CALORIES,
)

from .models import ExperienceLevel, Goal, NutritionTarget, Profile, TargetSource
from .repository import ProfileRepository
from .schemas import (
    DailyTargets,
    EstimateTargetsInput,
    OnboardingInput,
    ProfileRead,
    TargetEstimateRead,
    TargetVersionRead,
    TimezoneInput,
    UpdateProfileInput,
)

# A profile this young that sets its timezone is a new sign-up, not a user who travelled.
_NEW_ACCOUNT = timedelta(days=1)
# Given to a new profile, and used to judge days for a user who has no targets yet.
DEFAULT_TARGETS = DailyTargets(calories=2200, protein=150, carbs=230, fat=70)


def _one_decimal(value: float) -> float:
    """Round half up to one decimal, as the Numeric(6, 1) columns store it; round() takes 150.25 down."""

    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _stored_targets(targets: DailyTargets) -> DailyTargets:
    """The targets as stored. Macros are kept to one decimal, so compare at that precision;
    otherwise 150.25 (stored as 150.3) would never match and every resave would add a version."""

    return DailyTargets(
        calories=targets.calories,
        protein=_one_decimal(targets.protein),
        carbs=_one_decimal(targets.carbs),
        fat=_one_decimal(targets.fat),
    )


def _estimate(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    activity: ActivityLevel,
    goal: Goal,
    weekly_rate_kg: float,
) -> TargetEstimateRead:
    estimate = estimate_targets(
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        sex=sex,
        activity=activity,
        goal=goal.value,
        weekly_rate_kg=weekly_rate_kg,
        min_calories=MIN_TARGET_CALORIES,
        max_calories=MAX_TARGET_CALORIES,
        max_protein_g=MAX_TARGET_PROTEIN_G,
        max_carbs_g=MAX_TARGET_CARBS_G,
    )
    return TargetEstimateRead(**estimate._asdict())


def _untouched_defaults(history: list[NutritionTarget]) -> NutritionTarget | None:
    """The starting targets, if they're still the only version: defaults nothing has changed."""

    if len(history) == 1 and history[0].source == TargetSource.INITIAL:
        return history[0]
    return None


def _apply(profile: Profile, payload: UpdateProfileInput) -> None:
    profile.name = payload.name
    profile.height_cm = payload.height_cm
    profile.goal = payload.goal
    profile.weekly_rate_kg = payload.weekly_rate_kg
    profile.experience_level = payload.experience_level
    profile.date_of_birth = payload.date_of_birth
    profile.sex = payload.sex
    profile.activity_level = payload.activity_level
    profile.touch()


def to_daily_targets(target: NutritionTarget) -> DailyTargets:
    return DailyTargets(
        calories=target.calories,
        protein=float(target.protein_g),
        carbs=float(target.carbs_g),
        fat=float(target.fat_g),
    )


class ProfileService:
    def __init__(
        self,
        session: AsyncSession,
        repository: ProfileRepository,
        users: UserRepository,
        weigh_ins: WeighInRepository,
    ) -> None:
        self.session = session
        self.repository = repository
        self.users = users
        self.weigh_ins = weigh_ins

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
            experience_level=ExperienceLevel.BEGINNER,
        )
        try:
            # A savepoint, so losing the race below undoes only this insert.
            async with self.session.begin_nested():
                await self.repository.add(profile)
                await self._add_targets(profile, None, DEFAULT_TARGETS, TargetSource.INITIAL)
        except IntegrityError:
            # A new user's first page load asks for several things at once, and another of
            # those requests created the profile first: use that one.
            existing = await self.repository.get(actor.actor_id)
            if existing is None:
                raise
            return existing
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
            experience_level=profile.experience_level,
            timezone=profile.timezone,
            onboarded=profile.onboarded_utc is not None,
            date_of_birth=profile.date_of_birth,
            sex=profile.sex,
            activity_level=profile.activity_level,
        )

    async def get(self, actor: ActorContext) -> ProfileRead:
        profile = await self._get_or_create(actor)
        return await self._to_read(profile, actor)

    async def update(self, payload: UpdateProfileInput, actor: ActorContext) -> ProfileRead:
        profile = await self._get_or_create(actor)
        _apply(profile, payload)
        await self.session.commit()
        await self.session.refresh(profile)
        return await self._to_read(profile, actor)

    async def complete_onboarding(self, payload: OnboardingInput, actor: ActorContext) -> ProfileRead:
        """Save the sign-up guide in one go: the profile, a weigh-in for today, and the
        starting targets. Only once: afterwards each is changed on its own page (409)."""

        profile = await self._get_or_create(actor)
        if not await self.repository.mark_onboarded(profile.user_id, utc_now()):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Your profile is already set up. Change it on the Profile page."
            )
        _apply(profile, payload)
        today = local_today(user_zone(profile.timezone))
        try:
            await self.weigh_ins.upsert(profile.user_id, today, payload.weight_kg)
            await self._set_starting_targets(profile, _stored_targets(payload.targets))
            await self.session.commit()
        except IntegrityError:
            # A weigh-in or targets change saved at the same moment; nothing here was kept.
            await self.session.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Your weight or targets were just changed elsewhere, please retry"
            ) from None
        await self.session.refresh(profile)
        return await self._to_read(profile, actor)

    async def _set_starting_targets(self, profile: Profile, targets: DailyTargets) -> None:
        """The targets chosen in the guide replace the defaults a new profile starts with, rather
        than following them as a change: the defaults were never the user's. Anything set since
        (through the API) is kept, and the chosen targets follow it as a manual change."""

        history = await self.repository.target_history(profile.user_id)
        defaults = _untouched_defaults(history)
        if defaults is not None:
            # Keeping their date, so every day since sign-up is still judged against a target.
            if to_daily_targets(defaults) != targets:
                defaults.calories = targets.calories
                defaults.protein_g = targets.protein
                defaults.carbs_g = targets.carbs
                defaults.fat_g = targets.fat
                defaults.touch()
            return
        current = history[-1] if history else None
        if current is not None and to_daily_targets(current) == targets:
            return
        await self._add_targets(profile, current, targets, TargetSource.MANUAL)

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

        defaults = _untouched_defaults(await self.repository.target_history(profile.user_id))
        if defaults is None:
            return
        created = profile.created_utc
        if datetime.now(UTC) - created > _NEW_ACCOUNT:
            return
        defaults.effective_date = local_today(user_zone(profile.timezone))

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

    async def estimate_targets(
        self, payload: EstimateTargetsInput, actor: ActorContext
    ) -> TargetEstimateRead:
        """Starting targets from details not saved yet (the sign-up guide's). Only reads: a
        profile that doesn't exist yet isn't created for this."""

        profile = await self.repository.get(actor.actor_id)
        today = local_today(user_zone(profile.timezone if profile else None))
        return _estimate(
            payload.weight_kg,
            payload.height_cm,
            age_on(payload.date_of_birth, today),
            payload.sex,
            payload.activity_level,
            payload.goal,
            payload.weekly_rate_kg,
        )

    async def estimate_targets_from_profile(self, actor: ActorContext) -> TargetEstimateRead:
        """Starting targets from the saved profile and the latest weigh-in, to set again on
        the Profile page. Nothing is saved: the user decides."""

        profile = await self.repository.get(actor.actor_id)
        if (
            profile is None
            or profile.date_of_birth is None
            or profile.sex is None
            or profile.activity_level is None
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Add your date of birth, sex and activity level to your profile first.",
            )
        today = local_today(user_zone(profile.timezone))
        latest = await self.weigh_ins.latest(profile.user_id, today)
        if latest is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Log your weight first: the estimate starts from it."
            )
        return _estimate(
            float(latest.weight_kg),
            float(profile.height_cm),
            age_on(profile.date_of_birth, today),
            profile.sex,
            profile.activity_level,
            profile.goal,
            float(profile.weekly_rate_kg),
        )

    async def get_targets(self, actor: ActorContext) -> DailyTargets:
        profile = await self._get_or_create(actor)
        current = await self.repository.current_targets(profile.user_id)
        return to_daily_targets(current) if current else DEFAULT_TARGETS

    async def update_targets(self, payload: DailyTargets, actor: ActorContext) -> DailyTargets:
        """Record the targets as a new version from today; saving unchanged targets adds nothing."""

        profile = await self._get_or_create(actor)
        current = await self.repository.current_targets(profile.user_id)
        stored = _stored_targets(payload)
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
        """The latest ``MAX_TARGET_HISTORY`` versions of the targets, newest first."""

        profile = await self._get_or_create(actor)
        return [
            TargetVersionRead(
                **to_daily_targets(row).model_dump(),
                version=row.version,
                effective_date=row.effective_date,
                source=row.source,
                changed_at=row.created_utc,
            )
            for row in await self.repository.recent_targets(profile.user_id, MAX_TARGET_HISTORY)
        ]
