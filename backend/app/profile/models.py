"""Per-user fitness profile and nutrition targets."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence import Base, TimestampMixin


class Goal(StrEnum):
    LOSE = "lose"
    MAINTAIN = "maintain"
    GAIN = "gain"


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    height_cm: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    goal: Mapped[Goal] = mapped_column(SAEnum(Goal, name="profile_goal"), nullable=False)
    weekly_rate_kg: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    training_days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)

    target_calories: Mapped[int] = mapped_column(Integer, nullable=False)
    target_protein_g: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    target_carbs_g: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    target_fat_g: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
