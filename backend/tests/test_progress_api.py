from __future__ import annotations

from fastapi.testclient import TestClient


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
