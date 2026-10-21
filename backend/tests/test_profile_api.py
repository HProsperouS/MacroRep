from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.profile.models import Profile
from app.profile.repository import ProfileRepository
from tests.helpers import register_user


def test_get_profile_seeded(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/profile", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alex Tan"
    assert body["email"] == "alex.tan@example.com"
    assert body["goal"] == "lose"
    assert body["experienceLevel"] == "intermediate"
    assert body["equipment"] == ["barbell", "dumbbell", "bodyweight"]


def test_update_profile_round_trips(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "name": "Alex T.",
        "heightCm": 176,
        "goal": "maintain",
        "weeklyRateKg": 0,
        "trainingDaysPerWeek": 4,
        "experienceLevel": "advanced",
        "dateOfBirth": "1995-04-20",
        "sex": "female",
        "activityLevel": "moderate",
        "equipment": ["barbell", "kettlebell"],
    }
    response = client.put("/api/v1/profile", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alex T."
    assert body["goal"] == "maintain"
    assert body["trainingDaysPerWeek"] == 4
    assert body["experienceLevel"] == "advanced"
    assert body["equipment"] == ["barbell", "kettlebell"]


def test_update_profile_rejects_invalid_equipment(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "name": "Alex T.",
        "heightCm": 176,
        "goal": "maintain",
        "weeklyRateKg": 0,
        "trainingDaysPerWeek": 4,
        "experienceLevel": "advanced",
        "dateOfBirth": "1995-04-20",
        "sex": "female",
        "activityLevel": "moderate",
        "equipment": ["trampoline"],
    }
    response = client.put("/api/v1/profile", headers=auth_headers, json=payload)
    assert response.status_code == 422


def test_targets_round_trip(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/nutrition/targets", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["calories"] == 2350

    updated = {"calories": 2200, "protein": 160, "carbs": 220, "fat": 65}
    response = client.put("/api/v1/nutrition/targets", headers=auth_headers, json=updated)
    assert response.status_code == 200
    assert response.json() == updated


def test_a_profile_created_by_a_concurrent_first_request_is_used(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A new user's first page load sends several requests at once. Simulate one that
    # looked before another had created the profile, and so tries to create it too.
    headers = register_user(client)
    assert client.get("/api/v1/profile", headers=headers).status_code == 200
    real_get, real_add = ProfileRepository.get, ProfileRepository.add
    missed: list[str] = []
    collisions: list[IntegrityError] = []

    async def miss_once(self: ProfileRepository, user_id: str) -> Profile | None:
        if not missed:
            missed.append(user_id)
            return None
        return await real_get(self, user_id)

    async def recording_add(self: ProfileRepository, profile: Profile) -> Profile:
        try:
            return await real_add(self, profile)
        except IntegrityError as exc:
            collisions.append(exc)
            raise

    monkeypatch.setattr(ProfileRepository, "get", miss_once)
    monkeypatch.setattr(ProfileRepository, "add", recording_add)

    response = client.get("/api/v1/nutrition/targets", headers=headers)

    assert len(collisions) == 1  # it really did try to create the profile a second time
    assert response.status_code == 200
    history = client.get("/api/v1/nutrition/targets/history", headers=headers).json()
    assert len(history) == 1
