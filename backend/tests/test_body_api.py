from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_add_weigh_in(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {"date": date.today().isoformat(), "weightKg": 78.4}
    response = client.post("/api/body/weigh-ins", headers=auth_headers, json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["scaleKg"] == 78.4
    assert body["trendKg"] == 78.4  # first-ever weigh-in seeds the trend at the scale value


def test_add_weigh_in_rejects_non_positive_weight(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {"date": date.today().isoformat(), "weightKg": 0}
    response = client.post("/api/body/weigh-ins", headers=auth_headers, json=payload)
    assert response.status_code == 422
