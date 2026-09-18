"""Small database-query helpers shared across domain repositories."""

from __future__ import annotations

from typing import Protocol, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession


class _HasOwner(Protocol):
    owner_id: str


_OwnedModelT = TypeVar("_OwnedModelT", bound=_HasOwner)


async def get_owned(
    session: AsyncSession, model: type[_OwnedModelT], row_id: object, owner_id: str
) -> _OwnedModelT | None:
    """Fetch a row by primary key, but only if it belongs to ``owner_id``.

    Shared by every domain's "fetch my own record" lookup (food-log entries,
    coach check-ins, ...) so the owner check can't be forgotten in a new one.
    """

    row = await session.get(model, row_id)
    if row is None or row.owner_id != owner_id:
        return None
    return row


def escape_like(value: str, *, escape_char: str = "\\") -> str:
    """Escape SQL LIKE/ILIKE wildcards so a search term is matched literally.

    Without this, a query containing ``%`` or ``_`` (e.g. "100% Whole Wheat")
    is silently treated as a wildcard pattern instead of a literal string.
    Callers must pass the same ``escape_char`` to ``ilike(..., escape=...)``.
    """

    return (
        value.replace(escape_char, escape_char * 2)
        .replace("%", f"{escape_char}%")
        .replace("_", f"{escape_char}_")
    )
