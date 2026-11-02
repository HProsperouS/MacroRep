"""The demo account's history has to carry a live demo: a real check-in, and Progress to show."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.coach.models import CheckIn
from app.core.database import get_session_factory
from app.demo_seed import DEMO_TIMEZONE, seed_demo_history
from app.food.models import FoodEntry
from tests.helpers import ready_check_in, start_check_in


async def _without_a_check_in() -> None:
    """The client fixture adds one; the demo account starts with none."""

    async with get_session_factory()() as session:
        await session.execute(delete(CheckIn))
        await session.commit()


async def _entries() -> int | None:
    async with get_session_factory()() as session:
        return await session.scalar(select(func.count()).select_from(FoodEntry))


def _seeded(client: TestClient) -> None:
    client.portal.call(_without_a_check_in)
    client.portal.call(seed_demo_history)


def _snapshot(client: TestClient) -> dict[str, Any]:
    async def read() -> dict[str, Any]:
        async with get_session_factory()() as session:
            model = await session.scalar(select(CheckIn))
            assert model is not None
            return dict(model.input_snapshot)

    return client.portal.call(read)


def test_a_real_check_in_can_start_on_the_seeded_week(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    _seeded(client)

    assert start_check_in(client, auth_headers, "demo").status_code == 201
    check_in = ready_check_in(client, auth_headers)
    assert check_in["proposals"]

    week = _snapshot(client)
    assert abs(week["target_gap_kcal"]) < 150  # on target, so the slow loss is the finding
    assert abs(week["avg_calories"] - week["target_calories"]) < 50  # today's breakfast isn't a day
    assert -0.4 < week["weight_change_kg"] < 0  # slower than the 0.5 kg a week aimed for
    assert week["workouts_done"] == week["workouts_planned"] == 2
    assert week["missing_days"] == 0
    assert {routine["name"] for routine in week["routines"]} == {"Push day", "Pull day", "Leg day"}


def test_each_lift_tells_its_story(client: TestClient, auth_headers: dict[str, str]) -> None:
    _seeded(client)
    start_check_in(client, auth_headers, "demo")
    trends = _snapshot(client)["exercise_trends"]

    squat, pulldown = trends["exercise-squat"], trends["exercise-lat-pulldown"]
    assert squat["recent_avg_rpe"] > squat["prior_avg_rpe"]
    assert pulldown["recent_avg_rpe"] < pulldown["prior_avg_rpe"]


def test_today_is_left_to_log_live(client: TestClient, auth_headers: dict[str, str]) -> None:
    _seeded(client)
    today = datetime.now(ZoneInfo(DEMO_TIMEZONE)).date()

    assert client.get("/api/v1/workouts/today", headers=auth_headers).json()["name"] == "Push day"
    meals = client.get("/api/v1/food-log", params={"date": today.isoformat()}, headers=auth_headers).json()
    assert {entry["meal"] for entry in meals["entries"]} == {"breakfast"}

    yesterday = (today - timedelta(days=1)).isoformat()
    weigh_ins = client.get("/api/v1/body/weigh-ins", headers=auth_headers).json()
    assert yesterday in {weigh_in["date"] for weigh_in in weigh_ins}
    assert today.isoformat() not in {weigh_in["date"] for weigh_in in weigh_ins}


def test_seeding_twice_adds_nothing(client: TestClient) -> None:
    _seeded(client)
    entries = client.portal.call(_entries)

    client.portal.call(seed_demo_history)

    assert client.portal.call(_entries) == entries
