"""Bodyweight check-ins."""

from __future__ import annotations

import uuid
from datetime import date as date_

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence import Base, TimestampMixin


class WeighIn(TimestampMixin, Base):
    __tablename__ = "weigh_ins"
    __table_args__ = (Index("uq_weigh_ins_owner_date", "owner_id", "log_date", unique=True),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    log_date: Mapped[date_] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
