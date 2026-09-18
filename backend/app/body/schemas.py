"""Bodyweight API contracts."""

from __future__ import annotations

from datetime import date as date_

from pydantic import Field

from app.shared.schema import CamelModel


class WeighInInput(CamelModel):
    date: date_
    weight_kg: float = Field(gt=0)


class WeightPoint(CamelModel):
    date: date_
    scale_kg: float | None
    trend_kg: float
