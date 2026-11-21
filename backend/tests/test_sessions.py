"""Sessions: one signed-in device per user, so signing in elsewhere signs the previous device
out, and a device that's signed out (or whose password changed) loses access at once, not when
its access token would have expired."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.auth.service import MAX_SESSIONS_PER_USER
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.identity.models import User, UserSession, UserStatus
from app.main import app
from tests.fakes import FakeMailer
from tests.helpers import TEST_PASSWORD, login, register

ME = "/api/v1/users/me"
REFRESH = "/api/v1/auth/refresh"
NEW_PASSWORD = "a-brand-new-passphrase"


@pytest.fixture
def laptop(client: TestClient) -> Iterator[TestClient]:
    """A second device: the same app with a cookie jar of its own."""

    with TestClient(app) as other:
        yield other


def _bearer(response: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}  # type: ignore[attr-defined]


def _new_email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


def _sessions(client: TestClient, email: str) -> list[UserSession]:
    async def fetch() -> list[UserSession]:
        async with get_session_factory()() as session:
            user_id = await session.scalar(select(User.id).where(User.email == email))
            rows = await session.scalars(
                select(UserSession).where(UserSession.user_id == user_id).order_by(UserSession.created_utc)
            )
            return list(rows)

    return client.portal.call(fetch)


def test_signing_in_on_another_device_signs_the_first_out_at_once(
    client: TestClient, laptop: TestClient
) -> None:
    email = _new_email()
    phone = _bearer(register(client, email))

    computer = _bearer(login(laptop, email))

    # The phone is out straight away: its access token and its refresh cookie both.
    refused = client.get(ME, headers=phone)
    assert refused.status_code == 401
    assert refused.json()["detail"] == "Session ended"
    assert client.post(REFRESH).status_code == 401
    assert laptop.get(ME, headers=computer).status_code == 200
    assert laptop.post(REFRESH).status_code == 200
    assert len(_sessions(client, email)) == MAX_SESSIONS_PER_USER == 1


def test_signing_out_ends_the_session_at_once(client: TestClient) -> None:
    email = _new_email()
    headers = _bearer(register(client, email))
    cookie = client.cookies.get("macrorep_refresh")

    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204

    assert client.get(ME, headers=headers).status_code == 401
    client.cookies.set("macrorep_refresh", cookie or "")
    assert client.post(REFRESH).status_code == 401
    assert _sessions(client, email) == []


def test_changing_the_password_keeps_this_device_with_a_new_token(
    client: TestClient, mailer: FakeMailer
) -> None:
    email = _new_email()
    headers = _bearer(register(client, email))
    old_cookie = client.cookies.get("macrorep_refresh")

    changed = client.put(
        "/api/v1/auth/password",
        headers=headers,
        json={"currentPassword": TEST_PASSWORD, "newPassword": NEW_PASSWORD},
    )
    assert changed.status_code == 200
    new_cookie = client.cookies.get("macrorep_refresh")
    assert new_cookie and new_cookie != old_cookie

    # The same session carries on, so both access tokens work; the old cookie is retired.
    assert client.get(ME, headers=_bearer(changed)).status_code == 200
    assert client.get(ME, headers=headers).status_code == 200
    client.cookies.set("macrorep_refresh", old_cookie or "")
    assert client.post(REFRESH).status_code == 401
    assert len(_sessions(client, email)) == 1


def test_a_password_reset_ends_the_session_and_signs_in_here(
    client: TestClient, laptop: TestClient, mailer: FakeMailer
) -> None:
    email = _new_email()
    computer = _bearer(register(laptop, email))

    assert client.post("/api/v1/auth/password-reset", json={"email": email}).status_code == 202
    reset = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": email, "code": mailer.last_code(), "newPassword": NEW_PASSWORD},
    )
    assert reset.status_code == 200

    assert laptop.get(ME, headers=computer).status_code == 401
    assert laptop.post(REFRESH).status_code == 401
    assert client.get(ME, headers=_bearer(reset)).status_code == 200
    assert len(_sessions(client, email)) == 1


def test_an_expired_session_is_refused(client: TestClient) -> None:
    email = _new_email()
    headers = _bearer(register(client, email))

    async def expire() -> None:
        async with get_session_factory()() as session:
            await session.execute(
                update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await session.commit()

    client.portal.call(expire)
    assert client.get(ME, headers=headers).status_code == 401
    assert client.post(REFRESH).status_code == 401


def test_a_token_without_a_session_is_refused(client: TestClient) -> None:
    """Access tokens from before sessions carry no ``sid``: refused, so the client refreshes."""

    email = _new_email()
    register(client, email)
    user_id = client.get(ME, headers=_bearer(login(client, email))).json()["id"]
    settings = get_settings()
    now = datetime.now(UTC)
    legacy = jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=5)}, settings.jwt_secret_key
    )

    assert client.get(ME, headers={"Authorization": f"Bearer {legacy}"}).status_code == 401
    # The cookie still works, and its new token carries the session.
    assert client.get(ME, headers=_bearer(client.post(REFRESH))).status_code == 200


def test_a_disabled_account_is_refused_on_every_device(client: TestClient) -> None:
    email = _new_email()
    headers = _bearer(register(client, email))

    async def disable() -> None:
        async with get_session_factory()() as session:
            await session.execute(update(User).where(User.email == email).values(status=UserStatus.DISABLED))
            await session.commit()

    client.portal.call(disable)
    assert client.get(ME, headers=headers).status_code == 401
    assert client.post(REFRESH).status_code == 401
