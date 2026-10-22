"""Foods offered before a search: what the user ate lately, then catalog foods."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.food.catalog import POPULAR_FOOD_IDS
from tests.helpers import CHICKEN, EGG, iso_days_ago, log_food, quick_add, register_user

SUGGESTIONS = "/api/v1/foods/suggestions"
RICE = "food-white-rice"


def _ids(foods: list[dict[str, object]]) -> list[object]:
    return [food["id"] for food in foods]


def test_a_new_user_is_offered_catalog_foods(client: TestClient) -> None:
    headers = register_user(client)

    body = client.get(SUGGESTIONS, headers=headers).json()

    assert body["recent"] == []
    assert _ids(body["common"]) == list(POPULAR_FOOD_IDS[:8]), "the popular foods, most likely first"


def test_the_most_eaten_come_first_then_the_rest_of_the_catalog(client: TestClient) -> None:
    headers = register_user(client)
    log_food(client, headers, foodId=EGG, quantity=2)
    for _ in range(2):
        log_food(client, headers, foodId=CHICKEN, quantity=100, quantityUnit="g")
    quick_add(client, headers)  # not a food: left out

    body = client.get(SUGGESTIONS, headers=headers).json()

    assert _ids(body["recent"]) == [CHICKEN, EGG]
    assert CHICKEN not in _ids(body["common"]) and EGG not in _ids(body["common"]), "no food twice"
    assert _ids(body["common"]) == [food for food in POPULAR_FOOD_IDS if food not in (CHICKEN, EGG)][:6]


def test_the_popular_foods_fill_up_to_the_largest_limit(client: TestClient) -> None:
    headers = register_user(client)
    log_food(client, headers, foodId=POPULAR_FOOD_IDS[0], quantity=1)

    body = client.get(SUGGESTIONS, headers=headers, params={"limit": 20}).json()

    assert _ids(body["recent"]) + _ids(body["common"]) == list(POPULAR_FOOD_IDS)


def test_a_tie_goes_to_the_one_eaten_last(client: TestClient) -> None:
    headers = register_user(client)
    log_food(client, headers, foodId=RICE, quantity=1)
    log_food(client, headers, foodId=EGG, quantity=1)

    assert _ids(client.get(SUGGESTIONS, headers=headers).json()["recent"]) == [EGG, RICE]


def test_the_users_own_foods_count_and_others_never_show(client: TestClient) -> None:
    headers, someone_else = register_user(client), register_user(client)
    custom = {
        "name": "Mum's laksa",
        "servingSize": 1,
        "servingUnit": "bowl",
        "nutrition": {"calories": 600, "protein": 25, "carbs": 60, "fat": 28},
    }
    laksa = client.post("/api/v1/foods", headers=headers, json=custom).json()
    log_food(client, headers, foodId=laksa["id"], quantity=1)

    assert _ids(client.get(SUGGESTIONS, headers=headers).json()["recent"]) == [laksa["id"]]
    theirs = client.get(SUGGESTIONS, headers=someone_else).json()
    assert laksa["id"] not in _ids(theirs["recent"]) + _ids(theirs["common"])


def test_recent_means_eaten_in_the_last_month_whenever_it_was_logged(client: TestClient) -> None:
    headers = register_user(client)
    # A diary filled in today for last month counts by the days it's about.
    log_food(client, headers, date=iso_days_ago(40), foodId=EGG, quantity=1)
    log_food(client, headers, date=iso_days_ago(1), foodId=RICE, quantity=1)

    assert _ids(client.get(SUGGESTIONS, headers=headers).json()["recent"]) == [RICE]


def test_the_limit_bounds_both_lists_together(client: TestClient) -> None:
    headers = register_user(client)
    log_food(client, headers, foodId=EGG, quantity=1)

    body = client.get(SUGGESTIONS, headers=headers, params={"limit": 2}).json()

    assert len(body["recent"]) + len(body["common"]) == 2
    assert client.get(SUGGESTIONS, headers=headers, params={"limit": 21}).status_code == 422
