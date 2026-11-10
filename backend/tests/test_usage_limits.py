"""Per-user limits on the paid AI calls, counted in Postgres (app/shared/usage.py)."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select

from app.core.database import get_session_factory
from app.demo_seed import DEMO_USER_ID
from app.shared.exceptions import TooMany
from app.shared.rate_limit import Limit, limiter
from app.shared.usage import UsageEvent, counted_usage, give_back, give_back_latest, spend
from tests.helpers import usage_count

THREE_AN_HOUR = Limit(3, 60 * 60)


def run(client: TestClient, work: object) -> object:
    assert client.portal is not None
    return client.portal.call(work)  # type: ignore[arg-type]


def test_counts_survive_what_used_to_reset_them(client: TestClient) -> None:
    async def work() -> None:
        for _ in range(THREE_AN_HOUR.attempts):
            await spend("chat", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down.")
        limiter.reset()  # what a restart did to the in-memory counts
        with pytest.raises(TooMany) as refused:
            await spend("chat", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down.")
        assert str(refused.value).startswith("Slow down. Try again in")
        assert 0 < refused.value.retry_after <= 60 * 60

    run(client, work)
    assert usage_count(client, "chat") == THREE_AN_HOUR.attempts


def test_calls_made_at_once_cant_all_slip_under_the_limit(client: TestClient) -> None:
    async def work() -> list[object]:
        for _ in range(THREE_AN_HOUR.attempts - 1):
            await spend("photo", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down.")
        return await asyncio.gather(
            *(spend("photo", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down.") for _ in range(5)),
            return_exceptions=True,
        )

    results = run(client, work)
    assert isinstance(results, list)
    assert sum(isinstance(result, str) for result in results) == 1
    assert sum(isinstance(result, TooMany) for result in results) == 4
    assert usage_count(client, "photo") == THREE_AN_HOUR.attempts


def test_each_kind_and_user_counts_apart(client: TestClient) -> None:
    async def work() -> None:
        for _ in range(THREE_AN_HOUR.attempts):
            await spend("chat", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down.")
        await spend("photo", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down.")

    run(client, work)
    assert (usage_count(client, "chat"), usage_count(client, "photo")) == (3, 1)


def test_calls_past_the_window_no_longer_count_and_are_dropped(client: TestClient) -> None:
    async def work() -> None:
        async with get_session_factory()() as session, session.begin():
            now = (await session.execute(select(func.now()))).scalar_one()
            two_hours_ago = now - timedelta(hours=2)
            for index in range(THREE_AN_HOUR.attempts):
                await session.execute(
                    insert(UsageEvent).values(
                        id=f"old-{index}", kind="chat", owner_id=DEMO_USER_ID, created_utc=two_hours_ago
                    )
                )
        await spend("chat", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down.")

    run(client, work)
    assert usage_count(client, "chat") == 1, "the old ones went"


def test_a_count_can_be_given_back(client: TestClient) -> None:
    async def work() -> None:
        first = await spend("check_in", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down.")
        await spend("check_in", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down.")
        await give_back(first)
        await give_back_latest("check_in", DEMO_USER_ID)

    run(client, work)
    assert usage_count(client, "check_in") == 0


def test_a_block_that_fails_gives_its_count_back(client: TestClient) -> None:
    async def work() -> None:
        with pytest.raises(RuntimeError):
            async with counted_usage("chat", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down."):
                raise RuntimeError("model down")
        async with counted_usage("chat", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down."):
            pass
        async with counted_usage("chat", DEMO_USER_ID, THREE_AN_HOUR, reason="Slow down.", enabled=False):
            pass

    run(client, work)
    assert usage_count(client, "chat") == 1, "only the one that went through, and not the switched-off one"
