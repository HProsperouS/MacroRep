from __future__ import annotations

from fastapi.testclient import TestClient


def test_get_profile_seeded(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/profile", headers=auth_headers)
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
        "equipment": ["barbell", "kettlebell"],
    }
    response = client.put("/api/profile", headers=auth_headers, json=payload)
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
        "equipment": ["trampoline"],
    }
    response = client.put("/api/profile", headers=auth_headers, json=payload)
    assert response.status_code == 422


def test_targets_round_trip(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/nutrition/targets", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["calories"] == 2350

    updated = {"calories": 2200, "protein": 160, "carbs": 220, "fat": 65}
    response = client.put("/api/nutrition/targets", headers=auth_headers, json=updated)
    assert response.status_code == 200
    assert response.json() == updated
