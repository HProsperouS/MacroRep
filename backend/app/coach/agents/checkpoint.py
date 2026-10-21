"""Where the check-in graph keeps its state between steps.

``AsyncPostgresSaver`` stores each step's checkpoint in its own tables (created by
``setup()``), so a run interrupted by a restart resumes from its last finished step.
Until the app has started it, an in-memory saver stands in.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.database import libpq_conninfo

# Kept small: every connection counts against the database's limit (plan.md §22).
_POOL_MAX_SIZE = 2

_saver: BaseCheckpointSaver[str] = InMemorySaver()


def get_checkpointer() -> BaseCheckpointSaver[str]:
    return _saver


@asynccontextmanager
async def checkpointer_lifespan(database_url: str) -> AsyncIterator[None]:
    """Open the Postgres checkpointer for the app's lifetime."""

    global _saver
    async with AsyncConnectionPool(
        libpq_conninfo(database_url),
        min_size=1,
        max_size=_POOL_MAX_SIZE,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    ) as pool:
        saver = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
        await saver.setup()
        previous, _saver = _saver, saver
        try:
            yield
        finally:
            _saver = previous
