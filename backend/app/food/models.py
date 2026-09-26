"""Food catalog and daily food-log entries."""

from __future__ import annotations

import uuid
from datetime import date as date_
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence import Base, TimestampMixin

SERVING_UNITS = ("g", "ml", "piece", "bowl", "plate", "cup", "slice", "tbsp", "scoop")
MEAL_TYPES = ("breakfast", "lunch", "dinner", "snacks")
# How a food-log quantity was entered: a count of the food's servings, or grams.
QUANTITY_UNITS = ("serving", "g")


class FoodSource(StrEnum):
    DATABASE = "database"
    CUSTOM = "custom"
    QUICK_ADD = "quick-add"


class Food(TimestampMixin, Base):
    """A searchable food. Global catalog rows have ``owner_id`` unset."""

    __tablename__ = "foods"
    __table_args__ = (Index("ix_foods_owner_name", "owner_id", "name"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    serving_size: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    serving_unit: Mapped[str] = mapped_column(SAEnum(*SERVING_UNITS, name="serving_unit"), nullable=False)
    serving_weight_g: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    calories: Mapped[int] = mapped_column(nullable=False)
    protein: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    carbs: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    fat: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    fibre_g: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)
    sugar_g: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)
    sodium_mg: Mapped[float | None] = mapped_column(Numeric(7, 1), nullable=True)

    @property
    def source(self) -> FoodSource:
        return FoodSource.CUSTOM if self.owner_id else FoodSource.DATABASE


class FoodEntry(TimestampMixin, Base):
    """One logged item in a user's day.

    Name, amount label, and nutrition are stored on the entry itself, so the
    log never changes when a food's catalog values do. An entry logged from a
    saved food also keeps ``food_id`` and its quantity, which is what lets it
    be re-scaled later; quick adds have neither and are edited value by value.
    """

    __tablename__ = "food_entries"
    __table_args__ = (
        Index("ix_food_entries_owner_date", "owner_id", "log_date"),
        Index("ix_food_entries_food", "food_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    log_date: Mapped[date_] = mapped_column(Date, nullable=False)
    meal: Mapped[str] = mapped_column(SAEnum(*MEAL_TYPES, name="meal_type"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_label: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[FoodSource] = mapped_column(SAEnum(FoodSource, name="food_source"), nullable=False)
    calories: Mapped[int] = mapped_column(nullable=False)
    protein: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    carbs: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    fat: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    food_id: Mapped[str | None] = mapped_column(ForeignKey("foods.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(
        SAEnum(*QUANTITY_UNITS, name="quantity_unit"), nullable=True
    )
