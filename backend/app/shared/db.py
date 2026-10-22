"""Small database-query helpers shared across domain repositories."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from sqlalchemy import ColumnElement, case, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute


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


def name_search(
    name: QueryableAttribute[str], query: str
) -> tuple[list[ColumnElement[bool]], list[ColumnElement[Any]]]:
    """Filters and an ordering for searching ``name`` by ``query``, best match first.

    Every word of the query must appear in the name, in any order ("grilled chicken" finds
    "Chicken breast, grilled"). Matches rank by how the whole query meets the name: the
    name itself, then a name starting with it, then a word in the name starting with it,
    then anywhere. Within a rank, shorter names (the plainer food or movement) come first.
    """

    phrase = " ".join(query.split())
    if not phrase:
        return [], [name.asc()]
    filters: list[ColumnElement[bool]] = [
        name.ilike(f"%{escape_like(word)}%", escape="\\") for word in dict.fromkeys(phrase.split())
    ]
    escaped = escape_like(phrase)
    # A word starts after a space, a bracket, a hyphen or a slash ("Kopi-O", "Teh-C/O").
    word_start = or_(*(name.ilike(f"%{mark}{escaped}%", escape="\\") for mark in (" ", "(", "-", "/")))
    rank = case(
        # Both sides lower-cased by PostgreSQL, so they agree beyond ASCII too.
        (func.lower(name) == func.lower(phrase), 0),
        (name.ilike(f"{escaped}%", escape="\\"), 1),
        (word_start, 2),
        else_=3,
    )
    return filters, [rank, func.length(name), name.asc()]
