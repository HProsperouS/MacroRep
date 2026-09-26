from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient

from tests.helpers import register_user

ENTRIES = "/api/food-log/entries"
TODAY = date.today().isoformat()

# Seeded catalog foods (see app/demo_seed.py), nutrition per serving.
EGG = "food-egg"  # 1 piece (50 g): 78 kcal, 6.3 P, 0.6 C, 5.3 F
CHICKEN = "food-chicken-breast"  # 100 g: 165 kcal, 31 P, 0 C, 3.6 F


def _log_food(client: TestClient, headers: dict[str, str], **fields: Any) -> dict[str, Any]:
    response = client.post(ENTRIES, headers=headers, json={"date": TODAY, "meal": "lunch", **fields})
    assert response.status_code == 201, response.text
    return dict(response.json())


def _quick_add(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    return _log_food(
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


def _nutrition(entry: dict[str, Any]) -> tuple[Any, ...]:
    return (entry["calories"], entry["protein"], entry["carbs"], entry["fat"])


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


def test_logging_a_saved_food_derives_everything_from_the_food(client: TestClient) -> None:
    entry = _log_food(client, register_user(client), foodId=EGG, quantity=2, quantityUnit="serving")
    assert entry["name"] == "Egg, whole"
    assert entry["amountLabel"] == "2 piece · 100 g"
    assert entry["source"] == "database"
    assert _nutrition(entry) == (156, 12.6, 1.2, 10.6)
    assert (entry["foodId"], entry["quantity"], entry["quantityUnit"]) == (EGG, 2, "serving")


def test_logging_by_grams_converts_through_the_serving_weight(client: TestClient) -> None:
    # 50 g of a 100 g serving = 0.5 servings; 82.5 kcal rounds half up to 83, like the preview.
    entry = _log_food(client, register_user(client), foodId=CHICKEN, quantity=50, quantityUnit="g")
    assert entry["amountLabel"] == "50 g"
    assert _nutrition(entry) == (83, 15.5, 0.0, 1.8)


def test_grams_need_a_known_serving_weight(client: TestClient) -> None:
    headers = register_user(client)
    shake = client.post(
        "/api/foods",
        headers=headers,
        json={
            "name": "Shake",
            "servingSize": 1,
            "servingUnit": "scoop",
            "nutrition": {"calories": 120, "protein": 24, "carbs": 3, "fat": 1},
        },
    ).json()
    response = client.post(
        ENTRIES,
        headers=headers,
        json={"date": TODAY, "meal": "snacks", "foodId": shake["id"], "quantity": 30, "quantityUnit": "g"},
    )
    assert response.status_code == 422


def test_an_entry_is_either_a_saved_food_or_entered_values(client: TestClient) -> None:
    headers = register_user(client)
    base = {"date": TODAY, "meal": "lunch"}
    no_quantity = client.post(ENTRIES, headers=headers, json={**base, "foodId": EGG})
    assert no_quantity.status_code == 422
    nutrition_with_food = client.post(
        ENTRIES, headers=headers, json={**base, "foodId": EGG, "quantity": 1, "calories": 999}
    )
    assert nutrition_with_food.status_code == 422
    incomplete_quick_add = client.post(
        ENTRIES, headers=headers, json={**base, "name": "Snack", "calories": 100}
    )
    assert incomplete_quick_add.status_code == 422


def test_another_users_custom_food_is_not_visible(client: TestClient) -> None:
    owner = register_user(client)
    food = client.post(
        "/api/foods",
        headers=owner,
        json={
            "name": "Secret recipe",
            "servingSize": 1,
            "servingUnit": "bowl",
            "nutrition": {"calories": 300, "protein": 20, "carbs": 30, "fat": 10},
        },
    ).json()
    assert client.get(f"/api/foods/{food['id']}", headers=owner).status_code == 200

    intruder = register_user(client)
    assert client.get(f"/api/foods/{food['id']}", headers=intruder).status_code == 404
    # The global catalog is shared by everyone.
    assert client.get(f"/api/foods/{EGG}", headers=intruder).status_code == 200
    logged = client.post(
        ENTRIES, headers=intruder, json={"date": TODAY, "meal": "lunch", "foodId": food["id"], "quantity": 1}
    )
    assert logged.status_code == 404


def test_changing_the_quantity_rescales_the_entry(client: TestClient) -> None:
    headers = register_user(client)
    entry = _log_food(client, headers, foodId=EGG, quantity=2, quantityUnit="serving")

    three = client.patch(f"{ENTRIES}/{entry['id']}", headers=headers, json={"quantity": 3})
    assert three.status_code == 200
    assert three.json()["amountLabel"] == "3 piece · 150 g"
    assert _nutrition(three.json()) == (234, 18.9, 1.8, 15.9)

    # Switching to grams: 25 g of a 50 g egg is half a serving.
    grams = client.patch(
        f"{ENTRIES}/{entry['id']}", headers=headers, json={"quantity": 25, "quantityUnit": "g"}
    )
    assert grams.status_code == 200
    assert (grams.json()["quantity"], grams.json()["quantityUnit"]) == (25, "g")
    assert _nutrition(grams.json()) == (39, 3.2, 0.3, 2.7)


def test_an_entry_can_move_meal_and_day(client: TestClient) -> None:
    headers = register_user(client)
    entry = _log_food(client, headers, foodId=EGG, quantity=1)
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    moved = client.patch(
        f"{ENTRIES}/{entry['id']}", headers=headers, json={"meal": "dinner", "date": yesterday}
    )
    assert moved.status_code == 200
    assert moved.json()["meal"] == "dinner"

    def ids_on(day: str) -> list[str]:
        log = client.get("/api/food-log", headers=headers, params={"date": day}).json()
        return [row["id"] for row in log["entries"]]

    assert entry["id"] not in ids_on(TODAY)
    assert entry["id"] in ids_on(yesterday)


def test_a_quick_add_is_edited_value_by_value(client: TestClient) -> None:
    headers = register_user(client)
    entry = _quick_add(client, headers)

    edited = client.patch(
        f"{ENTRIES}/{entry['id']}", headers=headers, json={"name": "Chicken rice", "calories": 700}
    )
    assert edited.status_code == 200
    assert edited.json()["name"] == "Chicken rice"
    assert _nutrition(edited.json()) == (700, 30, 80, 20)  # untouched macros are kept

    # There's no food to scale a quick add from.
    rescaled = client.patch(f"{ENTRIES}/{entry['id']}", headers=headers, json={"quantity": 2})
    assert rescaled.status_code == 422


def test_a_saved_foods_nutrition_cant_be_overwritten_directly(client: TestClient) -> None:
    headers = register_user(client)
    entry = _log_food(client, headers, foodId=EGG, quantity=1)
    response = client.patch(f"{ENTRIES}/{entry['id']}", headers=headers, json={"calories": 10})
    assert response.status_code == 422


def test_another_users_entry_cannot_be_edited(client: TestClient) -> None:
    owner = register_user(client)
    entry = _quick_add(client, owner)
    intruder = register_user(client)
    response = client.patch(f"{ENTRIES}/{entry['id']}", headers=intruder, json={"calories": 1})
    assert response.status_code == 404
