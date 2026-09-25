from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

CHECK_INS = "/api/coach/check-ins"


def _new_user(client: TestClient) -> dict[str, str]:
    """A fresh account, so check-in tests don't see each other's (or the seed's) data."""

    registered = client.post(
        "/api/auth/register",
        json={
            "name": "Check-in Tester",
            "email": f"{uuid.uuid4().hex}@example.com",
            "password": "long-enough-pw",
        },
    )
    assert registered.status_code == 201
    return {"Authorization": f"Bearer {registered.json()['accessToken']}"}


def _log_food(client: TestClient, headers: dict[str, str], days_ago: int, calories: int = 2000) -> None:
    response = client.post(
        "/api/food-log/entries",
        headers=headers,
        json={
            "date": (date.today() - timedelta(days=days_ago)).isoformat(),
            "meal": "lunch",
            "name": "Test meal",
            "amountLabel": "1 plate",
            "source": "quick-add",
            "calories": calories,
            "protein": 100,
            "carbs": 200,
            "fat": 60,
        },
    )
    assert response.status_code == 201


def _weigh_in(client: TestClient, headers: dict[str, str], days_ago: int, weight_kg: float) -> None:
    response = client.post(
        "/api/body/weigh-ins",
        headers=headers,
        json={"date": (date.today() - timedelta(days=days_ago)).isoformat(), "weightKg": weight_kg},
    )
    assert response.status_code == 201


def _start(client: TestClient, headers: dict[str, str], key: str):
    return client.post(CHECK_INS, headers={**headers, "Idempotency-Key": key})


def test_current_check_in_seeded(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/coach/check-ins/current", headers=auth_headers)
    assert response.status_code == 200
    check_in = response.json()
    assert check_in is not None
    assert check_in["weekLabel"] == "Week 1"
    assert len(check_in["proposals"]) == 1


def test_decide_and_ask(client: TestClient, auth_headers: dict[str, str]) -> None:
    check_in = client.get("/api/coach/check-ins/current", headers=auth_headers).json()
    proposal_id = check_in["proposals"][0]["id"]

    decision = client.post(
        f"/api/coach/check-ins/{check_in['id']}/proposals/{proposal_id}/decision",
        headers=auth_headers,
        json={"decision": "apply"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "applied"

    reply = client.post(
        f"/api/coach/check-ins/{check_in['id']}/messages",
        headers=auth_headers,
        json={"text": "Why this change?"},
    )
    assert reply.status_code == 200
    assert reply.json()["role"] == "coach"

    # Deciding an already-decided proposal again must be rejected, not silently overwritten.
    redecision = client.post(
        f"/api/coach/check-ins/{check_in['id']}/proposals/{proposal_id}/decision",
        headers=auth_headers,
        json={"decision": "reject"},
    )
    assert redecision.status_code == 409


def test_start_check_in_requires_an_idempotency_key(client: TestClient) -> None:
    headers = _new_user(client)
    assert client.post(CHECK_INS, headers=headers).status_code == 422


def test_start_check_in_refuses_without_enough_data(client: TestClient) -> None:
    headers = _new_user(client)
    _log_food(client, headers, days_ago=0)
    _weigh_in(client, headers, days_ago=0, weight_kg=80)

    refused = _start(client, headers, "too-early")
    assert refused.status_code == 422
    assert "log food on at least 4" in refused.json()["detail"]
    assert "weigh in at least 2" in refused.json()["detail"]
    assert client.get(f"{CHECK_INS}/current", headers=headers).json() is None

    # A refusal doesn't consume the key: once the data exists, the same key succeeds.
    for days_ago in (1, 2, 3):
        _log_food(client, headers, days_ago=days_ago)
    _weigh_in(client, headers, days_ago=3, weight_kg=80.2)
    assert _start(client, headers, "too-early").status_code == 201


def test_replaying_an_idempotency_key_returns_the_same_check_in(client: TestClient) -> None:
    headers = _new_user(client)
    for days_ago in range(4):
        _log_food(client, headers, days_ago=days_ago)
    _weigh_in(client, headers, days_ago=5, weight_kg=80)
    _weigh_in(client, headers, days_ago=0, weight_kg=80)

    first = _start(client, headers, "week-1")
    assert first.status_code == 201
    check_in = first.json()
    assert check_in["weekLabel"] == "Week 1"
    # 4/7 days logged is below the placeholder pipeline's adherence bar, so no proposals.
    assert check_in["proposals"] == []
    assert check_in["status"] == "reviewed"

    replay = _start(client, headers, "week-1")
    assert replay.status_code == 200
    assert replay.json() == check_in

    assert client.get(f"{CHECK_INS}/current", headers=headers).json()["id"] == check_in["id"]

    # A different key is a different request: nothing is pending, so a new check-in is made.
    second = _start(client, headers, "week-2")
    assert second.status_code == 201
    assert second.json()["id"] != check_in["id"]
    assert second.json()["weekLabel"] == "Week 2"


def test_idempotency_keys_are_scoped_per_user(client: TestClient) -> None:
    ids = []
    for _ in range(2):
        headers = _new_user(client)
        for days_ago in range(4):
            _log_food(client, headers, days_ago=days_ago)
        _weigh_in(client, headers, days_ago=4, weight_kg=70)
        _weigh_in(client, headers, days_ago=0, weight_kg=70)
        response = _start(client, headers, "shared-key")
        assert response.status_code == 201
        ids.append(response.json()["id"])
    assert ids[0] != ids[1]


def test_pending_proposals_block_a_new_check_in(client: TestClient) -> None:
    headers = _new_user(client)
    # Every day logged (100% adherence) and the trend dropping 0.2 kg against a
    # maintain goal: enough for the placeholder pipeline to propose a change.
    for days_ago in range(7):
        _log_food(client, headers, days_ago=days_ago)
    _weigh_in(client, headers, days_ago=6, weight_kg=80)
    _weigh_in(client, headers, days_ago=0, weight_kg=78)

    first = _start(client, headers, "with-proposal")
    assert first.status_code == 201
    check_in = first.json()
    assert check_in["status"] == "needs-review"
    assert len(check_in["proposals"]) == 1

    blocked = _start(client, headers, "another-key")
    assert blocked.status_code == 409

    # Replaying the original key is still fine: it's a read, not a new check-in.
    assert _start(client, headers, "with-proposal").status_code == 200

    proposal_id = check_in["proposals"][0]["id"]
    decided = client.post(
        f"{CHECK_INS}/{check_in['id']}/proposals/{proposal_id}/decision",
        headers=headers,
        json={"decision": "reject"},
    )
    assert decided.status_code == 200
    assert _start(client, headers, "another-key").status_code == 201
