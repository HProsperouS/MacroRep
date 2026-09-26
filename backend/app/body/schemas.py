"""Bodyweight API contracts."""

from __future__ import annotations

from datetime import date as date_

from pydantic import Field

from app.shared.schema import CamelModel


class WeighInInput(CamelModel):
    date: date_
    weight_kg: float = Field(gt=0)


class UpdateWeighInInput(CamelModel):
    """Fields to change; anything omitted is left as it is."""

    date: date_ | None = None
    weight_kg: float | None = Field(default=None, gt=0)


class WeighInRead(CamelModel):
    id: str
    date: date_
    weight_kg: float
    trend_kg: float


class WeightPoint(CamelModel):
    date: date_
    scale_kg: float | None
    trend_kg: float
