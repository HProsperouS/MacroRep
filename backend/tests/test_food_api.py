from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_food_log_add_and_remove(client: TestClient, auth_headers: dict[str, str]) -> None:
    today = date.today().isoformat()
    entry_payload = {
        "date": today,
        "meal": "lunch",
        "name": "Chicken breast, grilled",
        "amountLabel": "150 g",
        "source": "database",
        "calories": 248,
        "protein": 46.5,
        "carbs": 0,
        "fat": 5.4,
    }
    created = client.post("/api/food-log/entries", headers=auth_headers, json=entry_payload)
    assert created.status_code == 201
    entry_id = created.json()["id"]

    log = client.get("/api/food-log", headers=auth_headers, params={"date": today})
    assert log.status_code == 200
    assert log.json()["date"] == today
    assert any(entry["id"] == entry_id for entry in log.json()["entries"])

    deleted = client.delete(f"/api/food-log/entries/{entry_id}", headers=auth_headers)
    assert deleted.status_code == 204

    log_after = client.get("/api/food-log", headers=auth_headers, params={"date": today})
    assert all(entry["id"] != entry_id for entry in log_after.json()["entries"])


def test_search_escapes_like_metacharacters(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = client.post(
        "/api/foods",
        headers=auth_headers,
        json={
            "name": "100% Whole Wheat Bread",
            "servingSize": 1,
            "servingUnit": "slice",
            "nutrition": {"calories": 80, "protein": 4, "carbs": 15, "fat": 1},
        },
    )
    assert created.status_code == 201

    # A literal '%' must not act as a SQL wildcard matching everything.
    matched = client.get("/api/foods", headers=auth_headers, params={"q": "100%"})
    assert matched.status_code == 200
    assert any(food["name"] == "100% Whole Wheat Bread" for food in matched.json())

    unrelated = client.get(
        "/api/foods", headers=auth_headers, params={"q": "100% Whole Wheat Bread and more"}
    )
    assert unrelated.status_code == 200
    assert unrelated.json() == []


def test_add_entry_rejects_invalid_meal(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "date": date.today().isoformat(),
        "meal": "brunch",
        "name": "Pancakes",
        "amountLabel": "1 plate",
        "source": "database",
        "calories": 400,
        "protein": 10,
        "carbs": 60,
        "fat": 12,
    }
    response = client.post("/api/food-log/entries", headers=auth_headers, json=payload)
    assert response.status_code == 422


def test_search_and_create_custom_food(client: TestClient, auth_headers: dict[str, str]) -> None:
    seeded = client.get("/api/foods", headers=auth_headers, params={"q": "chicken"})
    assert seeded.status_code == 200
    assert any(food["name"].lower().startswith("chicken") for food in seeded.json())

    custom_payload = {
        "name": "Homemade protein shake",
        "servingSize": 1,
        "servingUnit": "scoop",
        "nutrition": {"calories": 220, "protein": 30, "carbs": 10, "fat": 5},
    }
    created = client.post("/api/foods", headers=auth_headers, json=custom_payload)
    assert created.status_code == 201
    body = created.json()
    assert body["source"] == "custom"
    assert body["nutrition"]["calories"] == 220
