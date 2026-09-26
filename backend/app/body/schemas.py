"""Bodyweight API contracts."""

from __future__ import annotations

from datetime import date as date_

from pydantic import Field

from app.shared.schema import CamelModel
from app.shared.validation import MAX_BODY_WEIGHT_KG, MIN_BODY_WEIGHT_KG, LogDate


class WeighInInput(CamelModel):
    date: LogDate
    weight_kg: float = Field(ge=MIN_BODY_WEIGHT_KG, le=MAX_BODY_WEIGHT_KG)


class UpdateWeighInInput(CamelModel):
    """Fields to change; anything omitted is left as it is."""

    date: LogDate | None = None
    weight_kg: float | None = Field(default=None, ge=MIN_BODY_WEIGHT_KG, le=MAX_BODY_WEIGHT_KG)


class WeighInRead(CamelModel):
    id: str
    date: date_
    weight_kg: float
    trend_kg: float


class WeightPoint(CamelModel):
    date: date_
    scale_kg: float | None
    trend_kg: float
