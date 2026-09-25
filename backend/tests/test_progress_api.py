from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

from fastapi.testclient import TestClient

from app.analytics.training import week_start


def _new_user(client: TestClient) -> dict[str, str]:
    registered = client.post(
        "/api/auth/register",
        json={
            "name": "Progress Tester",
            "email": f"{uuid.uuid4().hex}@example.com",
            "password": "long-enough-pw",
        },
    )
    assert registered.status_code == 201
    return {"Authorization": f"Bearer {registered.json()['accessToken']}"}


def _log_session(client: TestClient, headers: dict[str, str], day: date, weight_kg: float, reps: int) -> None:
    started = datetime.combine(day, time(12, 0), tzinfo=UTC)
    response = client.post(
        "/api/workouts/sessions",
        headers=headers,
        json={
            "planId": None,
            "name": "Session",
            "startedAt": started.isoformat(),
            "finishedAt": (started + timedelta(hours=1)).isoformat(),
            "exercises": [
                {
                    "exerciseId": "exercise-bench-press",
                    "name": "Barbell Bench Press",
                    "sets": [{"kind": "working", "weightKg": weight_kg, "reps": reps}],
                }
            ],
        },
    )
    assert response.status_code == 201


def test_volume_compares_the_last_two_completed_weeks(client: TestClient) -> None:
    headers = _new_user(client)
    last_week = week_start(date.today()) - timedelta(days=7)
    _log_session(client, headers, last_week - timedelta(days=7), 100, 8)  # week before: 800 kg
    _log_session(client, headers, last_week, 100, 10)  # last completed week: 1000 kg
    _log_session(client, headers, date.today(), 100, 1)  # the unfinished current week is ignored

    volume = client.get("/api/progress", headers=headers, params={"range": "1M"}).json()["volume"]
    assert volume["lastWeekTonnes"] == 1.0
    assert volume["changePercent"] == 25.0
    assert volume["targetTonnes"] is None
    assert volume["averageTonnes"] > 0


def test_volume_change_is_null_without_a_week_to_compare_against(client: TestClient) -> None:
    headers = _new_user(client)
    _log_session(client, headers, week_start(date.today()) - timedelta(days=7), 100, 10)

    volume = client.get("/api/progress", headers=headers, params={"range": "1M"}).json()["volume"]
    assert volume["lastWeekTonnes"] == 1.0
    assert volume["changePercent"] is None


def test_progress_smoke(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/progress", headers=auth_headers, params={"range": "1M"})
    assert response.status_code == 200
    body = response.json()
    assert body["range"] == "1M"
    assert "weight" in body and "workouts" in body


def test_progress_rejects_bad_range(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/progress", headers=auth_headers, params={"range": "nope"})
    assert response.status_code == 422


def test_daily_calories(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/nutrition/daily-calories", headers=auth_headers, params={"days": 7})
    assert response.status_code == 200
    assert len(response.json()) == 7
