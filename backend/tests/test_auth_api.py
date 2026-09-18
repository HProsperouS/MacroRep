"""Self-issued auth over the wire.

The access token travels in response bodies; the refresh token travels in an
httpOnly cookie that the TestClient's jar carries for us, which is exactly how
a browser would behave.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.demo_seed import DEMO_USER_EMAIL, DEMO_USER_PASSWORD

PASSWORD = "correct-horse-battery"
COOKIE = "macrorep_refresh"


def _register(client: TestClient, email: str, password: str = PASSWORD, name: str = "Test User"):
    return client.post("/api/auth/register", json={"name": name, "email": email, "password": password})


def _login(client: TestClient, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _present(client: TestClient, refresh_token: str) -> None:
    """Force a specific refresh token into the jar, dropping whatever is there."""

    client.cookies.clear()
    client.cookies.set(COOKIE, refresh_token)


def test_register_returns_an_access_token_and_sets_the_refresh_cookie(client: TestClient) -> None:
    created = _register(client, "new.user@example.com")
    assert created.status_code == 201
    body = created.json()
    assert body["accessToken"]
    # The refresh token must not be readable from the response body.
    assert "refreshToken" not in body
    assert client.cookies.get(COOKIE)

    me = client.get("/api/users/me", headers=_bearer(body["accessToken"]))
    assert me.status_code == 200
    assert me.json()["name"] == "Test User"
    assert me.json()["email"] == "new.user@example.com"
    assert me.json()["id"].startswith("USR-")


def test_the_refresh_cookie_is_locked_down(client: TestClient) -> None:
    header = _register(client, "cookie@example.com").headers["set-cookie"]
    assert "HttpOnly" in header
    assert "Path=/api/auth" in header
    assert "samesite=strict" in header.lower()


def test_register_rejects_a_duplicate_email(client: TestClient) -> None:
    assert _register(client, "dupe@example.com").status_code == 201
    assert _register(client, "dupe@example.com").status_code == 409


def test_register_rejects_a_too_short_password(client: TestClient) -> None:
    assert _register(client, "short@example.com", password="short").status_code == 422


def test_email_is_matched_case_insensitively(client: TestClient) -> None:
    assert _register(client, "Mixed.Case@Example.com").status_code == 201
    assert _login(client, "mixed.case@example.com", PASSWORD).status_code == 200
    # The stored address is normalized, and the duplicate check sees through case.
    assert _register(client, "MIXED.CASE@example.com").status_code == 409


def test_login_succeeds_for_the_seeded_demo_user(client: TestClient) -> None:
    response = _login(client, DEMO_USER_EMAIL, DEMO_USER_PASSWORD)
    assert response.status_code == 200
    assert response.json()["accessToken"]
    assert client.cookies.get(COOKIE)


def test_login_rejects_bad_credentials_without_saying_which_was_wrong(client: TestClient) -> None:
    wrong_password = _login(client, DEMO_USER_EMAIL, "not-the-password")
    unknown_email = _login(client, "nobody@example.com", "not-the-password")
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_refresh_rotates_the_cookie_and_retires_the_old_token(client: TestClient) -> None:
    _register(client, "rotate@example.com")
    first = client.cookies.get(COOKIE)
    assert first

    rotated = client.post("/api/auth/refresh")
    assert rotated.status_code == 200
    assert rotated.json()["accessToken"]
    second = client.cookies.get(COOKIE)
    assert second and second != first

    # The token that was just rotated away must not work a second time.
    _present(client, first)
    assert client.post("/api/auth/refresh").status_code == 401

    _present(client, second)
    assert client.post("/api/auth/refresh").status_code == 200


def test_refresh_without_a_cookie_is_rejected(client: TestClient) -> None:
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_the_refresh_token(client: TestClient) -> None:
    tokens = _register(client, "logout@example.com").json()

    logged_out = client.post("/api/auth/logout", headers=_bearer(tokens["accessToken"]))
    assert logged_out.status_code == 204
    assert client.post("/api/auth/refresh").status_code == 401


def test_requests_without_credentials_are_rejected(client: TestClient) -> None:
    assert client.get("/api/users/me").status_code == 401
    assert client.get("/api/profile").status_code == 401


def test_an_unverifiable_bearer_token_is_rejected(client: TestClient) -> None:
    assert client.get("/api/users/me", headers=_bearer("not-a-real-token")).status_code == 401


def test_a_valid_access_token_authorizes_other_domains(client: TestClient) -> None:
    tokens = _register(client, "cross.domain@example.com").json()
    response = client.get("/api/nutrition/targets", headers=_bearer(tokens["accessToken"]))
    assert response.status_code == 200
    assert set(response.json()) == {"calories", "protein", "carbs", "fat"}
