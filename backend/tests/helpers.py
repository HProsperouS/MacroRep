"""Shared test helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def machine_timezone() -> str:
    """An IANA zone on this machine's current UTC offset.

    Tests build dates with ``date.today()``, the machine's clock, so their
    users must share it: otherwise the server's "today" (in the user's zone)
    differs for part of every day. Offsets that aren't whole hours fall back
    to UTC.
    """

    offset = datetime.now().astimezone().utcoffset() or timedelta(0)
    hours, remainder = divmod(int(offset.total_seconds()), 3600)
    if remainder or hours == 0:
        return "UTC"
    return f"Etc/GMT{-hours:+d}"  # POSIX-style: Etc/GMT-8 is UTC+8


def register_user(client: TestClient, timezone: str | None = None) -> dict[str, str]:
    """Register a fresh account and return its auth headers.

    The test database is shared across tests, so anything that counts or
    compares a user's records should use its own user rather than the seed's.
    The user's timezone matches this machine unless one is given.
    """

    registered = client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": f"{uuid.uuid4().hex}@example.com", "password": "long-enough-pw"},
    )
    assert registered.status_code == 201
    headers = {"Authorization": f"Bearer {registered.json()['accessToken']}"}
    zone = timezone or machine_timezone()
    assert client.put("/api/profile/timezone", headers=headers, json={"timezone": zone}).status_code == 200
    return headers


def plan_every_day(client: TestClient, headers: dict[str, str]) -> None:
    """Give the user a planned workout on all seven days of the week."""

    for day_of_week in range(7):
        response = client.put(
            f"/api/workouts/plan/{day_of_week}",
            headers=headers,
            json={
                "name": "Full body",
                "weekLabel": "Week 1",
                "estimatedMinutes": 45,
                "exercises": [
                    {
                        "exerciseId": "exercise-squat",
                        "restSeconds": 120,
                        "sets": [{"kind": "working", "targetWeightKg": 80, "targetReps": 5}],
                    }
                ],
            },
        )
        assert response.status_code == 200
