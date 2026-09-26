"""Shared test helpers."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def register_user(client: TestClient) -> dict[str, str]:
    """Register a fresh account and return its auth headers.

    The test database is shared across tests, so anything that counts or
    compares a user's records should use its own user rather than the seed's.
    """

    registered = client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": f"{uuid.uuid4().hex}@example.com", "password": "long-enough-pw"},
    )
    assert registered.status_code == 201
    return {"Authorization": f"Bearer {registered.json()['accessToken']}"}
