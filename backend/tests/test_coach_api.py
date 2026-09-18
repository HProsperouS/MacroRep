from __future__ import annotations

from fastapi.testclient import TestClient


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
