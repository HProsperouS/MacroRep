"""Input allow-list: every bounded field accepts its edge values and rejects just past them.

The limits live in ``app/shared/validation.py``. Each rule gets a value just
inside the limit (accepted) and just outside it (422), so a limit that's
missing, or off by one, fails here rather than in production, where an
oversized value can overflow a Postgres column and surface as a 500.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import register_user

TODAY = date.today()
PROFILE = {
    "name": "Alex",
    "heightCm": 175,
    "goal": "lose",
    "weeklyRateKg": -0.5,
    "experienceLevel": "beginner",
    "dateOfBirth": "1995-04-20",
    "sex": "female",
    "activityLevel": "moderate",
}
QUICK_ADD = {
    "date": TODAY.isoformat(),
    "meal": "lunch",
    "name": "Meal",
    "amountLabel": "Quick add",
    "source": "quick-add",
    "calories": 500,
    "protein": 20,
    "carbs": 50,
    "fat": 10,
}
CUSTOM_FOOD = {
    "name": "Granola",
    "servingSize": 50,
    "servingUnit": "g",
    "nutrition": {"calories": 220, "protein": 5, "carbs": 30, "fat": 9},
}
TARGETS = {"calories": 2200, "protein": 150, "carbs": 230, "fat": 70}


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    return register_user(client)


def _session(**overrides: Any) -> dict[str, Any]:
    started = datetime.now(UTC) - timedelta(hours=1)
    payload: dict[str, Any] = {
        "planId": None,
        "name": "Session",
        "startedAt": started.isoformat(),
        "finishedAt": (started + timedelta(minutes=50)).isoformat(),
        "exercises": [
            {
                "exerciseId": "exercise-squat",
                "name": "Squat",
                "sets": [{"kind": "working", "weightKg": 100, "reps": 5}],
            }
        ],
    }
    return {**payload, **overrides}


def _set(weight_kg: float = 100, reps: int = 5) -> dict[str, Any]:
    return _session(
        exercises=[
            {
                "exerciseId": "exercise-squat",
                "name": "Squat",
                "sets": [{"kind": "working", "weightKg": weight_kg, "reps": reps}],
            }
        ]
    )


# (description, method, path, payload, expected status)
CASES: list[tuple[str, str, str, dict[str, Any], int]] = [
    # Weigh-ins: 20-400 kg, dated from 2000 to tomorrow (timezone tolerance).
    ("weight at minimum", "POST", "/api/v1/body/weigh-ins", {"date": TODAY.isoformat(), "weightKg": 20}, 201),
    (
        "weight below minimum",
        "POST",
        "/api/v1/body/weigh-ins",
        {"date": TODAY.isoformat(), "weightKg": 19.9},
        422,
    ),
    (
        "weight at maximum",
        "POST",
        "/api/v1/body/weigh-ins",
        {"date": TODAY.isoformat(), "weightKg": 400},
        201,
    ),
    (
        "weight above maximum",
        "POST",
        "/api/v1/body/weigh-ins",
        {"date": TODAY.isoformat(), "weightKg": 400.1},
        422,
    ),
    ("earliest date", "POST", "/api/v1/body/weigh-ins", {"date": "2000-01-01", "weightKg": 80}, 201),
    ("before earliest date", "POST", "/api/v1/body/weigh-ins", {"date": "1999-12-31", "weightKg": 80}, 422),
    (
        "tomorrow (timezone tolerance)",
        "POST",
        "/api/v1/body/weigh-ins",
        {"date": (TODAY + timedelta(days=1)).isoformat(), "weightKg": 80},
        201,
    ),
    (
        "two days ahead",
        "POST",
        "/api/v1/body/weigh-ins",
        {"date": (TODAY + timedelta(days=2)).isoformat(), "weightKg": 80},
        422,
    ),
    # Profile: height 100-250 cm, as the forms allow; weekly rate has no health limit, only
    # the column's ±99.99; names up to 60 characters.
    ("height at minimum", "PUT", "/api/v1/profile", {**PROFILE, "heightCm": 100}, 200),
    ("height below minimum", "PUT", "/api/v1/profile", {**PROFILE, "heightCm": 99.9}, 422),
    ("height at maximum", "PUT", "/api/v1/profile", {**PROFILE, "heightCm": 250}, 200),
    ("height above maximum", "PUT", "/api/v1/profile", {**PROFILE, "heightCm": 250.1}, 422),
    ("name at maximum", "PUT", "/api/v1/profile", {**PROFILE, "name": "x" * 60}, 200),
    ("name above maximum", "PUT", "/api/v1/profile", {**PROFILE, "name": "x" * 61}, 422),
    ("fast weekly rate is allowed", "PUT", "/api/v1/profile", {**PROFILE, "weeklyRateKg": -5}, 200),
    ("rate at storage limit", "PUT", "/api/v1/profile", {**PROFILE, "weeklyRateKg": -99.99}, 200),
    ("rate beyond storage limit", "PUT", "/api/v1/profile", {**PROFILE, "weeklyRateKg": -100}, 422),
    ("whitespace-only name", "PUT", "/api/v1/profile", {**PROFILE, "name": "   "}, 422),
    # Targets: 1,000-6,000 kcal; protein up to 500 g, carbs 1,000 g, fat 400 g, as the forms
    # allow; calories consistent with macros.
    (
        "calories at minimum",
        "PUT",
        "/api/v1/nutrition/targets",
        {**TARGETS, "calories": 1_000, "protein": 50, "carbs": 100, "fat": 30},
        200,
    ),
    ("calories below minimum", "PUT", "/api/v1/nutrition/targets", {**TARGETS, "calories": 999}, 422),
    (
        "zero targets",
        "PUT",
        "/api/v1/nutrition/targets",
        {"calories": 0, "protein": 0, "carbs": 0, "fat": 0},
        422,
    ),
    ("calories at maximum", "PUT", "/api/v1/nutrition/targets", {**TARGETS, "calories": 6_000}, 200),
    ("calories above maximum", "PUT", "/api/v1/nutrition/targets", {**TARGETS, "calories": 6_001}, 422),
    (
        "protein at maximum",
        "PUT",
        "/api/v1/nutrition/targets",
        {**TARGETS, "calories": 3_000, "protein": 500},
        200,
    ),
    ("protein above maximum", "PUT", "/api/v1/nutrition/targets", {**TARGETS, "protein": 501}, 422),
    (
        "fat above maximum",
        "PUT",
        "/api/v1/nutrition/targets",
        {**TARGETS, "calories": 5_000, "fat": 401},
        422,
    ),
    (
        "carbs above maximum",
        "PUT",
        "/api/v1/nutrition/targets",
        {**TARGETS, "calories": 6_000, "carbs": 1_001},
        422,
    ),
    (
        "calories far below macros",
        "PUT",
        "/api/v1/nutrition/targets",
        {"calories": 100, "protein": 1_000, "carbs": 0, "fat": 0},
        422,
    ),
    # Quick add: same nutrition bounds, trimmed name.
    (
        "quick add at calorie maximum",
        "POST",
        "/api/v1/food-log/entries",
        {**QUICK_ADD, "calories": 10_000},
        201,
    ),
    (
        "quick add above calorie maximum",
        "POST",
        "/api/v1/food-log/entries",
        {**QUICK_ADD, "calories": 10_001},
        422,
    ),
    ("quick add macro above maximum", "POST", "/api/v1/food-log/entries", {**QUICK_ADD, "fat": 1_001}, 422),
    ("quick add whitespace name", "POST", "/api/v1/food-log/entries", {**QUICK_ADD, "name": "   "}, 422),
    (
        "quick add dated two days ahead",
        "POST",
        "/api/v1/food-log/entries",
        {**QUICK_ADD, "date": (TODAY + timedelta(days=2)).isoformat()},
        422,
    ),
    # Custom foods.
    ("custom food serving at maximum", "POST", "/api/v1/foods", {**CUSTOM_FOOD, "servingSize": 5_000}, 201),
    (
        "custom food serving above maximum",
        "POST",
        "/api/v1/foods",
        {**CUSTOM_FOOD, "servingSize": 5_001},
        422,
    ),
    (
        "custom food with nutrients the app doesn't use",
        "POST",
        "/api/v1/foods",
        {**CUSTOM_FOOD, "sodiumMg": 500},
        422,
    ),
    ("custom food whitespace name", "POST", "/api/v1/foods", {**CUSTOM_FOOD, "name": "  "}, 422),
    (
        "custom food calories far below macros",
        "POST",
        "/api/v1/foods",
        {**CUSTOM_FOOD, "nutrition": {"calories": 10, "protein": 50, "carbs": 30, "fat": 9}},
        422,
    ),
    # Workouts: sets up to 1,000 kg and 100 reps; sane times; bounded sizes.
    ("set weight at maximum", "POST", "/api/v1/workouts/sessions", _set(weight_kg=1_000), 201),
    ("set weight above maximum", "POST", "/api/v1/workouts/sessions", _set(weight_kg=1_000.5), 422),
    ("reps at maximum", "POST", "/api/v1/workouts/sessions", _set(reps=100), 201),
    ("reps above maximum", "POST", "/api/v1/workouts/sessions", _set(reps=101), 422),
    ("no exercises", "POST", "/api/v1/workouts/sessions", _session(exercises=[]), 422),
    (
        "finishes before it starts",
        "POST",
        "/api/v1/workouts/sessions",
        _session(
            startedAt=datetime.now(UTC).isoformat(),
            finishedAt=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        ),
        422,
    ),
    (
        "finishes in the future",
        "POST",
        "/api/v1/workouts/sessions",
        _session(finishedAt=(datetime.now(UTC) + timedelta(hours=1)).isoformat()),
        422,
    ),
    (
        "time without a timezone",
        "POST",
        "/api/v1/workouts/sessions",
        _session(startedAt="2026-01-01T10:00:00", finishedAt="2026-01-01T11:00:00"),
        422,
    ),
    (
        "too many sets for one exercise",
        "POST",
        "/api/v1/workouts/sessions",
        _session(
            exercises=[
                {
                    "exerciseId": "exercise-squat",
                    "name": "Squat",
                    "sets": [{"kind": "working", "weightKg": 60, "reps": 5}] * 51,
                }
            ]
        ),
        422,
    ),
    (
        "exercise with an unknown muscle",
        "POST",
        "/api/v1/exercises",
        {"name": "Mystery", "equipment": "barbell", "muscles": ["spleen"]},
        422,
    ),
    (
        "exercise with a repeated muscle",
        "POST",
        "/api/v1/exercises",
        {"name": "Mystery", "equipment": "barbell", "muscles": ["chest", "chest"]},
        422,
    ),
    # Exercise names 2-60 characters and up to 4 muscle groups, as the form allows.
    (
        "exercise name too short",
        "POST",
        "/api/v1/exercises",
        {"name": "X", "equipment": "barbell", "muscles": ["chest"]},
        422,
    ),
    (
        "exercise name too long",
        "POST",
        "/api/v1/exercises",
        {"name": "x" * 61, "equipment": "barbell", "muscles": ["chest"]},
        422,
    ),
    (
        "exercise with four muscles",
        "POST",
        "/api/v1/exercises",
        {"name": "Complex", "equipment": "barbell", "muscles": ["chest", "back", "shoulders", "core"]},
        201,
    ),
    (
        "exercise with five muscles",
        "POST",
        "/api/v1/exercises",
        {
            "name": "Complex",
            "equipment": "barbell",
            "muscles": ["chest", "back", "shoulders", "core", "glutes"],
        },
        422,
    ),
]


@pytest.mark.parametrize(
    ("method", "path", "payload", "expected"),
    [case[1:] for case in CASES],
    ids=[case[0] for case in CASES],
)
def test_bounds(
    client: TestClient,
    headers: dict[str, str],
    method: str,
    path: str,
    payload: dict[str, Any],
    expected: int,
) -> None:
    response = client.request(method, path, headers=headers, json=payload)
    assert response.status_code == expected, response.text


@pytest.mark.parametrize(
    ("path", "params", "expected"),
    [
        ("/api/v1/foods", {"q": "x" * 100}, 200),
        ("/api/v1/foods", {"q": "x" * 101}, 422),
        ("/api/v1/exercises", {"q": "x" * 101}, 422),
        ("/api/v1/exercises", {"muscle": "chest"}, 200),
        ("/api/v1/exercises", {"muscle": "spleen"}, 422),
    ],
    ids=[
        "food search at limit",
        "food search too long",
        "exercise search too long",
        "known muscle",
        "unknown muscle",
    ],
)
def test_query_bounds(
    client: TestClient, headers: dict[str, str], path: str, params: dict[str, str], expected: int
) -> None:
    assert client.get(path, headers=headers, params=params).status_code == expected


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_rejected_not_crashed(
    client: TestClient, headers: dict[str, str], token: str
) -> None:
    # Python's JSON parser accepts these tokens even though JSON doesn't define them.
    body = json.dumps({**PROFILE, "weeklyRateKg": 0}).replace('"weeklyRateKg": 0', f'"weeklyRateKg": {token}')
    response = client.put(
        "/api/v1/profile", headers={**headers, "Content-Type": "application/json"}, content=body
    )
    assert response.status_code == 422
    assert "finite" in response.json()["message"]


def test_validation_errors_never_echo_the_rejected_input(client: TestClient) -> None:
    secret = "correct-horse-battery-staple-" * 10  # too long, so it's rejected
    response = client.post(
        "/api/v1/auth/register", json={"name": "Alex", "email": "echo@example.com", "password": secret}
    )
    assert response.status_code == 422
    assert secret not in response.text
    assert all("input" not in error for error in response.json()["detail"])


HIDDEN_CHARACTERS = {
    "NUL byte": "Al\x00ex",
    "newline": "Alex\nTan",
    "terminal escape": "Alex\x1b[31m",
    "tab": "Alex\tTan",
    "right-to-left override": "Alex\u202egnp.exe",
    "directional isolate": "Alex\u2066Tan",
}
REAL_NAMES = {
    "accents": "José Müller",
    "non-Latin script": "김민준",
    "apostrophe and hyphen": "O'Brien-Smith",
    "emoji with joiners": "Alex 👨‍👩‍👧",
}

# Every single-line text field a client can set, as (path, method, payload builder).
TEXT_FIELDS: dict[str, tuple[str, str, Any]] = {
    "register name": (
        "POST",
        "/api/v1/auth/register",
        lambda text: {"name": text, "email": f"{uuid.uuid4().hex}@example.com", "password": "long-enough-pw"},
    ),
    "profile name": ("PUT", "/api/v1/profile", lambda text: {**PROFILE, "name": text}),
    "quick add name": ("POST", "/api/v1/food-log/entries", lambda text: {**QUICK_ADD, "name": text}),
    "custom food name": ("POST", "/api/v1/foods", lambda text: {**CUSTOM_FOOD, "name": text}),
    "exercise name": (
        "POST",
        "/api/v1/exercises",
        lambda text: {"name": text, "equipment": "barbell", "muscles": ["chest"]},
    ),
    "workout name": ("POST", "/api/v1/workouts/sessions", lambda text: _session(name=text)),
}


@pytest.mark.parametrize("field", TEXT_FIELDS, ids=list(TEXT_FIELDS))
@pytest.mark.parametrize("text", HIDDEN_CHARACTERS.values(), ids=list(HIDDEN_CHARACTERS))
def test_text_fields_reject_hidden_characters(
    client: TestClient, headers: dict[str, str], field: str, text: str
) -> None:
    method, path, build = TEXT_FIELDS[field]
    response = client.request(method, path, headers=headers, json=build(text))
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("field", TEXT_FIELDS, ids=list(TEXT_FIELDS))
@pytest.mark.parametrize("text", REAL_NAMES.values(), ids=list(REAL_NAMES))
def test_text_fields_accept_real_names(
    client: TestClient, headers: dict[str, str], field: str, text: str
) -> None:
    method, path, build = TEXT_FIELDS[field]
    response = client.request(method, path, headers=headers, json=build(text))
    assert response.status_code in (200, 201), response.text


@pytest.mark.parametrize(
    ("text", "expected"),
    [("First line\nsecond line", 200), ("Tabbed\tanswer", 200), ("Al\x00ex", 422), ("\u202ereversed", 422)],
    ids=["newline allowed", "tab allowed", "NUL rejected", "override rejected"],
)
def test_chat_allows_line_breaks_but_not_other_controls(
    client: TestClient, auth_headers: dict[str, str], text: str, expected: int
) -> None:
    check_in = client.get("/api/v1/coach/check-ins/current", headers=auth_headers).json()
    response = client.post(
        f"/api/v1/coach/check-ins/{check_in['id']}/messages", headers=auth_headers, json={"text": text}
    )
    assert response.status_code == expected


@pytest.mark.parametrize(
    "food_id",
    ["food\x00egg", "../etc/passwd", "food egg", "x" * 65, ""],
    ids=["NUL byte", "path characters", "space", "too long", "empty"],
)
def test_ids_in_bodies_must_look_like_ids(client: TestClient, headers: dict[str, str], food_id: str) -> None:
    response = client.post(
        "/api/v1/food-log/entries",
        headers=headers,
        json={"date": TODAY.isoformat(), "meal": "lunch", "foodId": food_id, "quantity": 1},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/foods/food-egg%00",
        "/api/v1/foods?q=%00",
        "/api/v1/foods?q=abc%00def",
        "/api/v1/food-log?date=2026-01-01%00",
    ],
    ids=["path", "query", "query middle", "query date"],
)
def test_nul_bytes_in_urls_are_refused(client: TestClient, headers: dict[str, str], url: str) -> None:
    response = client.get(url, headers=headers)
    assert response.status_code == 400
    assert "NUL" in response.json()["message"]


def test_text_is_stored_trimmed(client: TestClient, headers: dict[str, str]) -> None:
    response = client.put("/api/v1/profile", headers=headers, json={**PROFILE, "name": "  Alex Tan  "})
    assert response.status_code == 200
    assert response.json()["name"] == "Alex Tan"


@pytest.mark.parametrize(
    ("calories", "macros", "expected"),
    [
        (150, {"protein": 1.6, "carbs": 13, "fat": 0}, 201),  # beer: alcohol's energy has no macro
        (100, {"protein": 0, "carbs": 0, "fat": 0}, 201),  # a shot, or calories logged alone
        (300, {"protein": 25, "carbs": 25, "fat": 22.2}, 201),  # ~25% under: fibre and label rounding
        (200, {"protein": 100, "carbs": 0, "fat": 0}, 201),  # exactly half of 400 kcal: still allowed
        (199, {"protein": 100, "carbs": 0, "fat": 0}, 422),  # just under half
        (10, {"protein": 900, "carbs": 0, "fat": 0}, 422),  # a missing digit
        (0, {"protein": 10, "carbs": 0, "fat": 0}, 201),  # too small to judge (40 kcal)
    ],
    ids=["beer", "calories only", "fibre gap", "exactly half", "just under half", "missing digit", "tiny"],
)
def test_calories_are_checked_against_macros_one_way(
    client: TestClient, headers: dict[str, str], calories: int, macros: dict[str, float], expected: int
) -> None:
    response = client.post(
        "/api/v1/food-log/entries", headers=headers, json={**QUICK_ADD, "calories": calories, **macros}
    )
    assert response.status_code == expected, response.text


def test_editing_a_quick_add_rechecks_the_merged_values(client: TestClient, headers: dict[str, str]) -> None:
    entry = client.post(
        "/api/v1/food-log/entries", headers=headers, json=QUICK_ADD
    ).json()  # 500 kcal, 20/50/10
    # Calories alone would pass any bound, but against the kept macros (370 kcal) it's implausible.
    response = client.patch(f"/api/v1/food-log/entries/{entry['id']}", headers=headers, json={"calories": 50})
    assert response.status_code == 422
    assert "too low for these macros" in response.json()["detail"]
