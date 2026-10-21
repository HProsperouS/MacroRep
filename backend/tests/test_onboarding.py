"""The sign-up guide: the profile, today's weight and the starting targets, saved once."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import register_user

ONBOARDING = "/api/v1/profile/onboarding"
GUIDE: dict[str, Any] = {
    "name": "Sam Lee",
    "heightCm": 168,
    "goal": "lose",
    "weeklyRateKg": -0.5,
    "trainingDaysPerWeek": 4,
    "experienceLevel": "intermediate",
    "dateOfBirth": "1995-04-20",
    "sex": "female",
    "activityLevel": "moderate",
    "equipment": ["barbell", "dumbbell"],
    "weightKg": 72.4,
    "targets": {"calories": 1900, "protein": 140, "carbs": 190, "fat": 63},
}


def _history(client: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    return list(client.get("/api/v1/nutrition/targets/history", headers=headers).json())


def _weigh_ins(client: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    today = date.today().isoformat()
    params = {"from": today, "to": today}
    return list(client.get("/api/v1/body/weigh-ins", headers=headers, params=params).json())


def test_a_new_account_starts_with_the_guide_and_the_demo_user_doesnt(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    headers = register_user(client)

    assert client.get("/api/v1/profile", headers=headers).json()["onboarded"] is False
    assert client.get("/api/v1/profile", headers=auth_headers).json()["onboarded"] is True


def test_the_guide_saves_the_profile_todays_weight_and_the_starting_targets(client: TestClient) -> None:
    headers = register_user(client)

    response = client.post(ONBOARDING, headers=headers, json=GUIDE)

    assert response.status_code == 200
    profile = response.json()
    assert profile["onboarded"] is True
    assert (profile["name"], profile["heightCm"], profile["goal"], profile["weeklyRateKg"]) == (
        "Sam Lee",
        168,
        "lose",
        -0.5,
    )
    assert (profile["trainingDaysPerWeek"], profile["experienceLevel"], profile["equipment"]) == (
        4,
        "intermediate",
        ["barbell", "dumbbell"],
    )
    assert client.get("/api/v1/profile", headers=headers).json() == profile
    [weigh_in] = _weigh_ins(client, headers)
    assert weigh_in["weightKg"] == 72.4
    assert client.get("/api/v1/nutrition/targets", headers=headers).json() == GUIDE["targets"]
    [version] = _history(client, headers)
    assert (version["version"], version["source"], version["calories"]) == (1, "initial", 1900), (
        "the chosen targets replace the defaults rather than following them"
    )


def test_the_guide_is_finished_only_once(client: TestClient) -> None:
    headers = register_user(client)
    assert client.post(ONBOARDING, headers=headers, json=GUIDE).status_code == 200

    changed = {**GUIDE, "name": "Someone Else", "weightKg": 90}
    again = client.post(ONBOARDING, headers=headers, json=changed)

    assert again.status_code == 409
    assert "Profile page" in again.json()["detail"]
    assert client.get("/api/v1/profile", headers=headers).json()["name"] == "Sam Lee"
    assert [row["weightKg"] for row in _weigh_ins(client, headers)] == [72.4]
    assert len(_history(client, headers)) == 1


def test_an_invalid_guide_saves_nothing(client: TestClient) -> None:
    headers = register_user(client)

    for bad in (
        {**GUIDE, "weightKg": 5},
        {**GUIDE, "targets": {"calories": 1000, "protein": 200, "carbs": 300, "fat": 100}},
        {key: value for key, value in GUIDE.items() if key != "targets"},
    ):
        assert client.post(ONBOARDING, headers=headers, json=bad).status_code == 422

    assert client.get("/api/v1/profile", headers=headers).json()["onboarded"] is False
    assert _weigh_ins(client, headers) == []


def test_keeping_the_default_targets_changes_nothing(client: TestClient) -> None:
    headers = register_user(client)
    defaults = client.get("/api/v1/nutrition/targets", headers=headers).json()

    assert client.post(ONBOARDING, headers=headers, json={**GUIDE, "targets": defaults}).status_code == 200

    [version] = _history(client, headers)
    assert (version["source"], version["calories"]) == ("initial", defaults["calories"])


def test_targets_changed_before_the_guide_are_kept_in_the_history(client: TestClient) -> None:
    headers = register_user(client)
    changed = {"calories": 2000, "protein": 150, "carbs": 200, "fat": 67}
    assert client.put("/api/v1/nutrition/targets", headers=headers, json=changed).status_code == 200

    assert client.post(ONBOARDING, headers=headers, json=GUIDE).status_code == 200

    assert [(row["source"], row["calories"]) for row in _history(client, headers)] == [
        ("manual", 1900),
        ("manual", 2000),
        ("initial", 2200),
    ]


def test_a_clash_with_a_change_saved_at_the_same_moment_is_a_retryable_409(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.exc import IntegrityError

    headers = register_user(client)

    async def clash(*_: object) -> None:
        raise IntegrityError("INSERT", {}, Exception("uq_weigh_ins_owner_date"))

    monkeypatch.setattr("app.body.repository.WeighInRepository.upsert", clash)
    response = client.post(ONBOARDING, headers=headers, json=GUIDE)

    assert response.status_code == 409
    assert "retry" in response.json()["detail"]
    monkeypatch.undo()
    assert client.get("/api/v1/profile", headers=headers).json()["onboarded"] is False, "nothing was kept"
    assert client.post(ONBOARDING, headers=headers, json=GUIDE).status_code == 200


def test_targets_chosen_days_after_sign_up_still_cover_the_days_before(client: TestClient) -> None:
    from datetime import timedelta

    from sqlalchemy import update

    from app.core.database import get_session_factory
    from app.profile.models import NutritionTarget

    headers = register_user(client)
    _history(client, headers)  # the profile and its starting targets now exist
    user_id = client.get("/api/v1/users/me", headers=headers).json()["id"]
    signed_up = date.today() - timedelta(days=3)

    async def sign_up_days_ago() -> None:
        async with get_session_factory()() as session:
            await session.execute(
                update(NutritionTarget)
                .where(NutritionTarget.owner_id == user_id)
                .values(effective_date=signed_up)
            )
            await session.commit()

    assert client.portal is not None
    client.portal.call(sign_up_days_ago)

    assert client.post(ONBOARDING, headers=headers, json=GUIDE).status_code == 200

    [version] = _history(client, headers)
    assert (version["effectiveDate"], version["calories"]) == (signed_up.isoformat(), 1900)
