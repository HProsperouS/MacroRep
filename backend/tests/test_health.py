from __future__ import annotations

from fastapi.testclient import TestClient


def test_live(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_requires_actor(client: TestClient) -> None:
    response = client.get("/api/profile")
    assert response.status_code == 401
