from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.helpers import register_user

WEIGH_INS = "/api/body/weigh-ins"


def _day(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


def _weigh_in(client: TestClient, headers: dict[str, str], days_ago: int, weight_kg: float) -> None:
    response = client.post(WEIGH_INS, headers=headers, json={"date": _day(days_ago), "weightKg": weight_kg})
    assert response.status_code == 201


def _list(client: TestClient, headers: dict[str, str], **params: str) -> list[dict]:
    response = client.get(WEIGH_INS, headers=headers, params=params)
    assert response.status_code == 200
    return list(response.json())


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


def test_list_returns_the_range_newest_first_with_trend(client: TestClient) -> None:
    headers = register_user(client)
    _weigh_in(client, headers, days_ago=10, weight_kg=80)
    _weigh_in(client, headers, days_ago=5, weight_kg=78)
    _weigh_in(client, headers, days_ago=1, weight_kg=79)

    listed = _list(client, headers, **{"from": _day(6), "to": _day(0)})
    assert [row["date"] for row in listed] == [_day(1), _day(5)]
    # Trend is computed over full history, so the 80 kg reading outside the range still counts.
    assert listed[1]["trendKg"] == 79.8  # 80 + 0.1 * (78 - 80)
    assert listed[0]["weightKg"] == 79


def test_list_defaults_to_the_last_90_days(client: TestClient) -> None:
    headers = register_user(client)
    _weigh_in(client, headers, days_ago=100, weight_kg=80)
    _weigh_in(client, headers, days_ago=3, weight_kg=79)
    assert [row["date"] for row in _list(client, headers)] == [_day(3)]


def test_list_rejects_backwards_or_oversized_ranges(client: TestClient) -> None:
    headers = register_user(client)
    backwards = client.get(WEIGH_INS, headers=headers, params={"from": _day(0), "to": _day(5)})
    assert backwards.status_code == 422
    too_long = client.get(WEIGH_INS, headers=headers, params={"from": _day(400), "to": _day(0)})
    assert too_long.status_code == 422


def test_update_weight_and_move_date(client: TestClient) -> None:
    headers = register_user(client)
    _weigh_in(client, headers, days_ago=2, weight_kg=80)
    weigh_in_id = _list(client, headers)[0]["id"]

    corrected = client.patch(f"{WEIGH_INS}/{weigh_in_id}", headers=headers, json={"weightKg": 79.5})
    assert corrected.status_code == 200
    assert corrected.json()["weightKg"] == 79.5

    moved = client.patch(f"{WEIGH_INS}/{weigh_in_id}", headers=headers, json={"date": _day(1)})
    assert moved.status_code == 200
    assert moved.json() == {"id": weigh_in_id, "date": _day(1), "weightKg": 79.5, "trendKg": 79.5}
    assert [row["date"] for row in _list(client, headers)] == [_day(1)]


def test_moving_onto_a_taken_date_is_a_conflict(client: TestClient) -> None:
    headers = register_user(client)
    _weigh_in(client, headers, days_ago=2, weight_kg=80)
    _weigh_in(client, headers, days_ago=1, weight_kg=79)
    older = _list(client, headers)[1]

    response = client.patch(f"{WEIGH_INS}/{older['id']}", headers=headers, json={"date": _day(1)})
    assert response.status_code == 409
    # Nothing changed.
    assert [(row["date"], row["weightKg"]) for row in _list(client, headers)] == [
        (_day(1), 79),
        (_day(2), 80),
    ]


def test_delete_weigh_in(client: TestClient) -> None:
    headers = register_user(client)
    _weigh_in(client, headers, days_ago=1, weight_kg=80)
    weigh_in_id = _list(client, headers)[0]["id"]

    assert client.delete(f"{WEIGH_INS}/{weigh_in_id}", headers=headers).status_code == 204
    assert _list(client, headers) == []
    assert client.delete(f"{WEIGH_INS}/{weigh_in_id}", headers=headers).status_code == 404


def test_another_users_weigh_in_is_not_found(client: TestClient) -> None:
    owner = register_user(client)
    _weigh_in(client, owner, days_ago=1, weight_kg=80)
    weigh_in_id = _list(client, owner)[0]["id"]

    intruder = register_user(client)
    assert _list(client, intruder) == []
    patched = client.patch(f"{WEIGH_INS}/{weigh_in_id}", headers=intruder, json={"weightKg": 50})
    assert patched.status_code == 404
    assert client.delete(f"{WEIGH_INS}/{weigh_in_id}", headers=intruder).status_code == 404
    assert _list(client, owner)[0]["weightKg"] == 80
