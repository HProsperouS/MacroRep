"""Shared test helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from fastapi.testclient import TestClient
from httpx2 import Response

TEST_PASSWORD = "long-enough-pw"


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
        "/api/v1/auth/register",
        json={"name": "Test User", "email": f"{uuid.uuid4().hex}@example.com", "password": TEST_PASSWORD},
    )
    assert registered.status_code == 201
    headers = {"Authorization": f"Bearer {registered.json()['accessToken']}"}
    zone = timezone or machine_timezone()
    assert client.put("/api/v1/profile/timezone", headers=headers, json={"timezone": zone}).status_code == 200
    return headers


def plan_every_day(client: TestClient, headers: dict[str, str]) -> None:
    """Give the user a planned workout on all seven days of the week."""

    created = client.post(
        "/api/v1/workouts/routines",
        headers=headers,
        json={
            "name": "Full body",
            "exercises": [
                {
                    "exerciseId": "exercise-squat",
                    "restSeconds": 120,
                    "sets": [{"kind": "working", "targetWeightKg": 80, "targetReps": 5}],
                }
            ],
        },
    )
    assert created.status_code == 201
    for day_of_week in range(7):
        response = client.put(
            f"/api/v1/workouts/plan/{day_of_week}", headers=headers, json={"routineId": created.json()["id"]}
        )
        assert response.status_code == 200


def iso_days_ago(days: int) -> str:
    """The date ``days`` before today, as the API takes it."""

    return (date.today() - timedelta(days=days)).isoformat()


def register(
    client: TestClient, email: str, password: str = TEST_PASSWORD, name: str = "Test User"
) -> Response:
    return client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": password})


def login(client: TestClient, email: str, password: str = TEST_PASSWORD) -> Response:
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# --- Food -------------------------------------------------------------------------------------

FOOD_ENTRIES = "/api/v1/food-log/entries"
# Catalog foods (app/food/catalog.py), nutrition per serving.
EGG = "food-egg"  # 1 piece (50 g): 78 kcal, 6.3 P, 0.6 C, 5.3 F
CHICKEN = "food-chicken-breast"  # 100 g: 165 kcal, 31 P, 0 C, 3.6 F


def log_food(client: TestClient, headers: dict[str, str], **fields: Any) -> dict[str, Any]:
    """Log an entry for lunch today, with ``fields`` for the rest."""

    response = client.post(
        FOOD_ENTRIES, headers=headers, json={"date": date.today().isoformat(), "meal": "lunch", **fields}
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def quick_add(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    return log_food(
        client,
        headers,
        name="Hawker lunch",
        amountLabel="Quick add",
        source="quick-add",
        calories=650,
        protein=30,
        carbs=80,
        fat=20,
    )


def log_meal(client: TestClient, headers: dict[str, str], days_ago: int, calories: int = 2000) -> None:
    """A quick-add lunch of ``calories`` on the day ``days_ago``. The check-in and Progress count
    calories only, so the macros are left at zero (and a small meal is never refused as implausible)."""

    log_food(
        client,
        headers,
        date=iso_days_ago(days_ago),
        name="Test meal",
        amountLabel="1 plate",
        source="quick-add",
        calories=calories,
        protein=0,
        carbs=0,
        fat=0,
    )


# --- Body and profile -------------------------------------------------------------------------


def weigh_in(client: TestClient, headers: dict[str, str], days_ago: int, weight_kg: float) -> None:
    response = client.post(
        "/api/v1/body/weigh-ins",
        headers=headers,
        json={"date": iso_days_ago(days_ago), "weightKg": weight_kg},
    )
    assert response.status_code == 201, response.text


def target_history(client: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    response = client.get("/api/v1/nutrition/targets/history", headers=headers)
    assert response.status_code == 200
    return list(response.json())


ONBOARDING = "/api/v1/profile/onboarding"
GUIDE: dict[str, Any] = {
    "name": "Sam Lee",
    "heightCm": 168,
    "goal": "lose",
    "weeklyRateKg": -0.5,
    "experienceLevel": "intermediate",
    "dateOfBirth": "1995-04-20",
    "sex": "female",
    "activityLevel": "moderate",
    "weightKg": 72.4,
    "targets": {"calories": 1900, "protein": 140, "carbs": 190, "fat": 63},
}


# --- Workouts ---------------------------------------------------------------------------------


def log_bench(
    client: TestClient, headers: dict[str, str], days_ago: int, weight_kg: float, rpe: float
) -> None:
    """Three working sets of five on the bench press, at noon UTC on the day ``days_ago``."""

    started = datetime.combine(date.today() - timedelta(days=days_ago), time(12, 0), tzinfo=UTC)
    sets = [{"kind": "working", "weightKg": weight_kg, "reps": 5, "rpe": rpe}] * 3
    response = client.post(
        "/api/v1/workouts/sessions",
        headers=headers,
        json={
            "planId": None,
            "name": "Push",
            "startedAt": started.isoformat(),
            "finishedAt": (started + timedelta(hours=1)).isoformat(),
            "exercises": [
                {"exerciseId": "exercise-bench-press", "name": "Barbell Bench Press", "sets": sets}
            ],
        },
    )
    assert response.status_code == 201


# --- Coach ------------------------------------------------------------------------------------

CHECK_INS = "/api/v1/coach/check-ins"


def start_check_in(client: TestClient, headers: dict[str, str], key: str) -> Response:
    return client.post(CHECK_INS, headers={**headers, "Idempotency-Key": key})


def current_check_in(client: TestClient, headers: dict[str, str]) -> Any:
    response = client.get(f"{CHECK_INS}/current", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def ready_check_in(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    """The current check-in once generated. The test client runs the background
    generation before the POST returns, so it has always finished by now."""

    check_in = current_check_in(client, headers)
    assert check_in["status"] not in ("running", "failed"), check_in
    return dict(check_in)


def week_with_a_proposal(client: TestClient, headers: dict[str, str]) -> None:
    """Every day logged and the trend off a maintain goal: the fake model proposes a calorie change."""

    for days_ago in range(7):
        log_meal(client, headers, days_ago=days_ago)
    weigh_in(client, headers, days_ago=6, weight_kg=80)
    weigh_in(client, headers, days_ago=0, weight_kg=78)


def training_check_in(client: TestClient, headers: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """A routine (warm-up + 3 x 100 kg x 5 bench) and a check-in proposing to ease it to 95 kg."""

    routine = client.post(
        "/api/v1/workouts/routines",
        headers=headers,
        json={
            "name": "Push",
            "exercises": [
                {
                    "exerciseId": "exercise-bench-press",
                    "restSeconds": 120,
                    "sets": [
                        {"kind": "warmup", "targetWeightKg": 40, "targetReps": 10},
                        *[{"kind": "working", "targetWeightKg": 100, "targetReps": 5}] * 3,
                    ],
                }
            ],
        },
    ).json()
    for day in range(7):
        client.put(f"/api/v1/workouts/plan/{day}", headers=headers, json={"routineId": routine["id"]})
    week_with_a_proposal(client, headers)
    log_bench(client, headers, days_ago=14, weight_kg=100, rpe=8)
    log_bench(client, headers, days_ago=2, weight_kg=95, rpe=9.5)
    log_bench(client, headers, days_ago=1, weight_kg=95, rpe=9.5)
    start_check_in(client, headers, "training")
    check_in = ready_check_in(client, headers)
    training = next(p for p in check_in["proposals"] if p["kind"] == "training")
    return routine, {**check_in, "proposals": [training]}


def decide(
    client: TestClient,
    headers: dict[str, str],
    check_in: dict[str, Any],
    body: dict[str, Any],
    proposal_id: str | None = None,
) -> Response:
    """Decide one of the check-in's proposals, its first unless ``proposal_id`` says which."""

    proposal_id = proposal_id or check_in["proposals"][0]["id"]
    return client.post(
        f"{CHECK_INS}/{check_in['id']}/proposals/{proposal_id}/decision", headers=headers, json=body
    )


def ask_coach(client: TestClient, headers: dict[str, str], check_in_id: str, text: str) -> Response:
    return client.post(f"{CHECK_INS}/{check_in_id}/messages", headers=headers, json={"text": text})
