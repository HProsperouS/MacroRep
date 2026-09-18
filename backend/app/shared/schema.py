"""Shared Pydantic base that speaks the frontend's camelCase JSON convention."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.title() for part in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


def validate_choice(value: str, allowed: Sequence[str], field_name: str) -> str:
    """Shared body for the several `@field_validator`s that check a string
    field against a fixed set of allowed values (e.g. an enum-backed DB
    column), so an out-of-range value fails Pydantic validation with a clean
    422 instead of reaching the database and raising there."""

    if value not in allowed:
        raise ValueError(f"{field_name} must be one of {tuple(allowed)}")
    return value
