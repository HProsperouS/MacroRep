"""The user's timezone decides their calendar days: unit rules and API behaviour."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.shared.timezones import is_known_timezone, local_date, local_today, user_zone, utc_bounds
from tests.helpers import plan_every_day
from tests.helpers import register_user as _new_user

SINGAPORE = ZoneInfo("Asia/Singapore")  # UTC+8, no daylight saving
# UTC+14: its calendar day differs from UTC's for most of the day, whenever the tests run.
KIRITIMATI = "Pacific/Kiritimati"


def test_utc_bounds_cover_the_local_days() -> None:
    since, until = utc_bounds(date(2026, 9, 28), date(2026, 9, 28), SINGAPORE)
    assert since == datetime(2026, 9, 27, 16, 0, tzinfo=UTC)  # Singapore midnight
    assert until == datetime(2026, 9, 28, 16, 0, tzinfo=UTC)  # the next midnight, exclusive


def test_an_early_morning_session_belongs_to_the_local_day() -> None:
    # 7 a.m. Monday in Singapore is 11 p.m. Sunday in UTC.
    sunday_night_utc = datetime(2026, 9, 27, 23, 0, tzinfo=UTC)
    assert local_date(sunday_night_utc, SINGAPORE) == date(2026, 9, 28)
    assert local_date(sunday_night_utc, SINGAPORE).weekday() == 0


def test_naive_timestamps_are_read_as_utc() -> None:
    # SQLite returns stored timestamps without their offset.
    assert local_date(datetime(2026, 9, 27, 23, 0), SINGAPORE) == date(2026, 9, 28)


@pytest.mark.parametrize("name", [None, "", "Mars/Olympus_Mons", "../../etc/passwd"])
def test_unknown_zones_fall_back_to_utc(name: str | None) -> None:
    assert user_zone(name) == ZoneInfo("UTC")


def test_only_iana_names_are_known() -> None:
    assert is_known_timezone("Asia/Singapore")
    assert not is_known_timezone("asia/singapore")
    assert not is_known_timezone("/etc/localtime")


def test_profile_timezone_can_be_set_and_read(client: TestClient) -> None:
    headers = _new_user(client)
    response = client.put("/api/profile/timezone", headers=headers, json={"timezone": "Asia/Singapore"})
    assert response.status_code == 200
    assert response.json()["timezone"] == "Asia/Singapore"
    assert client.get("/api/profile", headers=headers).json()["timezone"] == "Asia/Singapore"


@pytest.mark.parametrize("timezone", ["Mars/Olympus_Mons", "../../etc/passwd", "", "x" * 65])
def test_unknown_timezones_are_rejected(client: TestClient, timezone: str) -> None:
    headers = _new_user(client)
    response = client.put("/api/profile/timezone", headers=headers, json={"timezone": timezone})
    assert response.status_code == 422


def _log_bench(client: TestClient, headers: dict[str, str], started: datetime) -> None:
    response = client.post(
        "/api/workouts/sessions",
        headers=headers,
        json={
            "planId": None,
            "name": "Session",
            "startedAt": started.isoformat(),
            "finishedAt": (started + timedelta(minutes=1)).isoformat(),
            "exercises": [
                {
                    "exerciseId": "exercise-bench-press",
                    "name": "Barbell Bench Press",
                    "sets": [{"kind": "working", "weightKg": 60, "reps": 8}],
                }
            ],
        },
    )
    assert response.status_code == 201


def test_last_session_is_dated_in_the_users_timezone(client: TestClient) -> None:
    headers = _new_user(client, timezone=KIRITIMATI)
    zone = ZoneInfo(KIRITIMATI)
    yesterday = local_today(zone) - timedelta(days=1)
    # 7 a.m. there is 5 p.m. the previous day in UTC.
    _log_bench(client, headers, datetime.combine(yesterday, time(7, 0), tzinfo=zone))

    exercises = client.get("/api/exercises", headers=headers, params={"q": "Barbell Bench Press"}).json()
    bench = next(exercise for exercise in exercises if exercise["id"] == "exercise-bench-press")
    assert bench["lastSession"]["date"] == yesterday.isoformat()


def test_training_today_counts_in_the_users_timezone(client: TestClient) -> None:
    headers = _new_user(client, timezone=KIRITIMATI)
    plan_every_day(client, headers)
    _log_bench(client, headers, datetime.now(UTC) - timedelta(minutes=2))

    workouts = client.get("/api/progress", headers=headers, params={"range": "1M"}).json()["workouts"]
    # 29 finished plan days, plus today's once trained: today is Kiritimati's today.
    assert workouts == {"done": 1, "planned": 30, "completionPercent": 3.3}
