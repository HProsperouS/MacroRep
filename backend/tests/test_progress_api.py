from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from fastapi.testclient import TestClient

from app.analytics.training import week_start
from tests.helpers import register_user as _new_user


def _log_session(client: TestClient, headers: dict[str, str], day: date, weight_kg: float, reps: int) -> None:
    started = datetime.combine(day, time(12, 0), tzinfo=UTC)
    finished = started + timedelta(hours=1)
    if day == date.today():
        # Noon may still be ahead, and a workout can't finish in the future.
        finished = datetime.now(UTC)
        started = finished - timedelta(minutes=1)
    response = client.post(
        "/api/workouts/sessions",
        headers=headers,
        json={
            "planId": None,
            "name": "Session",
            "startedAt": started.isoformat(),
            "finishedAt": finished.isoformat(),
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
    assert len(response.json()["days"]) == 7


def _set_calorie_target(client: TestClient, headers: dict[str, str], calories: int) -> None:
    response = client.put(
        "/api/nutrition/targets",
        headers=headers,
        json={"calories": calories, "protein": 150, "carbs": 200, "fat": 60},
    )
    assert response.status_code == 200


def _log_calories(client: TestClient, headers: dict[str, str], days_ago: int, calories: int) -> None:
    response = client.post(
        "/api/food-log/entries",
        headers=headers,
        json={
            "date": (date.today() - timedelta(days=days_ago)).isoformat(),
            "meal": "lunch",
            "name": "Test meal",
            "amountLabel": "1 plate",
            "source": "quick-add",
            "calories": calories,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
        },
    )
    assert response.status_code == 201


def _log_mixed_week(client: TestClient) -> dict[str, str]:
    """A 2000 kcal target with one complete, one under-target, and one partial day, plus a snack today."""

    headers = _new_user(client)
    _set_calorie_target(client, headers, 2000)
    _log_calories(client, headers, days_ago=1, calories=2000)  # complete, on target
    _log_calories(client, headers, days_ago=2, calories=1500)  # complete, 500 under
    _log_calories(client, headers, days_ago=3, calories=600)  # partial: under half the target
    _log_calories(client, headers, days_ago=0, calories=300)  # today: in progress, not judged
    return headers


def test_progress_reports_logging_completeness_and_the_gap_to_target(client: TestClient) -> None:
    headers = _log_mixed_week(client)

    body = client.get("/api/progress", headers=headers, params={"range": "1M"}).json()
    # 1M is 30 days ending today; the 29 finished ones are judged.
    assert body["logging"] == {
        "completeDays": 2,
        "partialDays": 1,
        "missingDays": 26,
        "targetAdherencePercent": 33.3,  # only the 2000 kcal day is within ±10%
        "targetGapKcal": -1900,  # the partial day's 600 kcal counts as eaten
    }
    assert body["adherencePercent"] == 10.3  # 3 of 29 finished days logged


def test_daily_calories_label_each_day_and_total_the_gap(client: TestClient) -> None:
    headers = _log_mixed_week(client)

    body = client.get("/api/nutrition/daily-calories", headers=headers, params={"days": 7}).json()
    assert body["targetCalories"] == 2000
    assert body["targetGapKcal"] == -1900
    assert [day["status"] for day in body["days"]] == [
        "missing",
        "missing",
        "missing",
        "partial",
        "complete",
        "complete",
        "in-progress",
    ]
    assert body["days"][-1]["calories"] == 300
