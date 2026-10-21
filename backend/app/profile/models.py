"""Per-user fitness profile and nutrition targets."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.analytics.energy import ActivityLevel, Sex
from app.shared.persistence import Base, TimestampMixin
from app.shared.timezones import DEFAULT_TIMEZONE


class Goal(StrEnum):
    LOSE = "lose"
    MAINTAIN = "maintain"
    GAIN = "gain"


class TargetSource(StrEnum):
    """Where a version of the nutrition targets came from."""

    INITIAL = "initial"
    MANUAL = "manual"
    CHECK_IN = "check-in"


class ExperienceLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    height_cm: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    goal: Mapped[Goal] = mapped_column(SAEnum(Goal, name="profile_goal"), nullable=False)
    weekly_rate_kg: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        SAEnum(ExperienceLevel, name="experience_level"), nullable=False, default=ExperienceLevel.BEGINNER
    )
    # IANA name (e.g. "Asia/Singapore"), kept in sync from the browser. Decides
    # the user's "today" and which day a workout falls on (app.shared.timezones).
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default=DEFAULT_TIMEZONE, server_default=DEFAULT_TIMEZONE
    )
    # When the user finished the sign-up guide; until then the app shows only the guide.
    onboarded_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # For estimating starting targets (app.analytics.energy). Empty until the sign-up guide
    # asks for them; saving a profile requires them.
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[Sex | None] = mapped_column(SAEnum(Sex, name="profile_sex"), nullable=True)
    activity_level: Mapped[ActivityLevel | None] = mapped_column(
        SAEnum(ActivityLevel, name="activity_level"), nullable=True
    )


class NutritionTarget(TimestampMixin, Base):
    """One version of a user's daily nutrition targets.

    A change never overwrites the targets: it adds a version that takes effect
    on ``effective_date`` (the user's local day). The current targets are the
    highest version, and a past day is judged against the version in effect on
    it, so changing a target today doesn't rewrite how last week looks.
    """

    __tablename__ = "nutrition_targets"
    __table_args__ = (Index("uq_nutrition_targets_owner_version", "owner_id", "version", unique=True),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    calories: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_g: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    carbs_g: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    fat_g: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    source: Mapped[TargetSource] = mapped_column(
        SAEnum(TargetSource, name="nutrition_target_source"), nullable=False
    )
    # The check-in proposal that set these targets, when ``source`` is CHECK_IN.
    proposal_id: Mapped[str | None] = mapped_column(
        ForeignKey("coach_proposals.id", ondelete="SET NULL"), nullable=True
    )
