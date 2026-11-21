"""Changing the sign-in email: a code goes to the new address, and only that code makes the change."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, update

from app.core.config import Settings
from app.core.database import get_session_factory
from app.identity.models import EmailChangeRequest
from tests.fakes import FakeMailer
from tests.helpers import TEST_PASSWORD, login, register

REQUEST = "/api/v1/auth/email-change"
CONFIRM = "/api/v1/auth/email-change/confirm"


def _new_account(client: TestClient) -> tuple[str, dict[str, str]]:
    email = f"{uuid.uuid4().hex}@example.com"
    registered = register(client, email)
    assert registered.status_code == 201
    return email, {"Authorization": f"Bearer {registered.json()['accessToken']}"}


def _ask(client: TestClient, headers: dict[str, str], new_email: str, password: str = TEST_PASSWORD) -> int:
    return client.post(
        REQUEST, headers=headers, json={"newEmail": new_email, "password": password}
    ).status_code


def _pending(client: TestClient) -> list[EmailChangeRequest]:
    async def fetch() -> list[EmailChangeRequest]:
        async with get_session_factory()() as session:
            return list(await session.scalars(select(EmailChangeRequest)))

    return client.portal.call(fetch)


def test_the_code_sent_to_the_new_email_changes_it(client: TestClient, mailer: FakeMailer) -> None:
    old, headers = _new_account(client)
    new = f"New.{uuid.uuid4().hex}@Example.com"

    assert _ask(client, headers, f"  {new} ") == 202
    assert mailer.sent[-1].to == new.lower()
    # Nothing changes until the code is confirmed.
    assert client.get("/api/v1/users/me", headers=headers).json()["email"] == old

    confirmed = client.post(CONFIRM, headers=headers, json={"code": mailer.last_code()})
    assert confirmed.status_code == 200
    assert confirmed.json()["email"] == new.lower()
    assert client.get("/api/v1/users/me", headers=headers).json()["email"] == new.lower()
    assert client.get("/api/v1/profile", headers=headers).json()["email"] == new.lower()

    # The old address is told, and the code can't be used twice.
    assert mailer.sent[-1].to == old
    assert new.lower() in mailer.sent[-1].body
    assert client.post(CONFIRM, headers=headers, json={"code": "000000"}).status_code == 422

    assert login(client, new.lower()).status_code == 200
    assert login(client, old).status_code == 401


def test_asking_needs_the_right_password_and_a_new_free_email(client: TestClient, mailer: FakeMailer) -> None:
    old, headers = _new_account(client)
    taken, _ = _new_account(client)

    # 403, not 401: the session is fine, and a 401 would make the client refresh and retry.
    assert _ask(client, headers, "fresh@example.com", password="wrong-password") == 403
    assert _ask(client, headers, old.upper()) == 422
    assert _ask(client, headers, taken) == 409
    assert _ask(client, headers, "not-an-email") == 422
    assert (
        client.post(REQUEST, json={"newEmail": "x@example.com", "password": TEST_PASSWORD}).status_code == 401
    )
    assert mailer.sent == []


def test_a_wrong_code_is_refused_and_five_end_the_request(client: TestClient, mailer: FakeMailer) -> None:
    _, headers = _new_account(client)
    assert _ask(client, headers, f"{uuid.uuid4().hex}@example.com") == 202
    code = mailer.last_code()
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"

    for _ in range(4):
        refused = client.post(CONFIRM, headers=headers, json={"code": wrong})
        assert refused.status_code == 422
        assert refused.json()["detail"] == "That code isn't right"
    fifth = client.post(CONFIRM, headers=headers, json={"code": wrong})
    assert "Too many wrong codes" in fifth.json()["detail"]

    # Even the right code no longer works.
    assert client.post(CONFIRM, headers=headers, json={"code": code}).status_code == 422
    assert client.post(CONFIRM, headers=headers, json={"code": "12345"}).status_code == 422


def test_an_expired_code_is_refused(client: TestClient, mailer: FakeMailer) -> None:
    old, headers = _new_account(client)
    assert _ask(client, headers, f"{uuid.uuid4().hex}@example.com") == 202

    async def expire() -> None:
        async with get_session_factory()() as session:
            await session.execute(
                update(EmailChangeRequest).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await session.commit()

    client.portal.call(expire)
    refused = client.post(CONFIRM, headers=headers, json={"code": mailer.last_code()})
    assert refused.status_code == 422
    assert "expired" in refused.json()["detail"]
    assert client.get("/api/v1/users/me", headers=headers).json()["email"] == old
    assert _pending(client) == []


def test_asking_again_replaces_the_code_and_cancelling_drops_it(
    client: TestClient, mailer: FakeMailer
) -> None:
    _, headers = _new_account(client)
    assert _ask(client, headers, f"{uuid.uuid4().hex}@example.com") == 202
    first = mailer.last_code()
    second_email = f"{uuid.uuid4().hex}@example.com"
    assert _ask(client, headers, second_email) == 202
    second = mailer.last_code()
    assert len(_pending(client)) == 1

    if first != second:
        assert client.post(CONFIRM, headers=headers, json={"code": first}).status_code == 422
    assert client.delete(REQUEST, headers=headers).status_code == 204
    assert client.post(CONFIRM, headers=headers, json={"code": second}).status_code == 422
    assert _pending(client) == []


def test_a_code_that_cant_be_sent_can_be_asked_for_again(client: TestClient, mailer: FakeMailer) -> None:
    _, headers = _new_account(client)
    new = f"{uuid.uuid4().hex}@example.com"
    mailer.fail = True

    # Sent after answering, so a mail failure can't fail (or slow down) the request.
    assert _ask(client, headers, new) == 202
    assert mailer.sent == []

    mailer.fail = False
    assert _ask(client, headers, new) == 202
    assert client.post(CONFIRM, headers=headers, json={"code": mailer.last_code()}).status_code == 200


def test_a_failed_notice_to_the_old_email_still_changes_it(client: TestClient, mailer: FakeMailer) -> None:
    _, headers = _new_account(client)
    new = f"{uuid.uuid4().hex}@example.com"
    assert _ask(client, headers, new) == 202
    code = mailer.last_code()
    mailer.fail = True

    assert client.post(CONFIRM, headers=headers, json={"code": code}).status_code == 200
    assert client.get("/api/v1/users/me", headers=headers).json()["email"] == new


def test_codes_asked_for_are_rate_limited(client: TestClient, mailer: FakeMailer) -> None:
    _, headers = _new_account(client)
    for _ in range(5):
        assert _ask(client, headers, f"{uuid.uuid4().hex}@example.com") == 202
    limited = client.post(
        REQUEST, headers=headers, json={"newEmail": "late@example.com", "password": TEST_PASSWORD}
    )
    assert limited.status_code == 429
    assert "Too many codes" in limited.json()["detail"]
    assert len(mailer.sent) == 5


def test_production_needs_smtp() -> None:
    values = {
        "DATABASE_URL": "postgresql+psycopg://localhost/unused",
        "APP_ENV": "prod",
        "PREVIEW_AUTH_ENABLED": "false",
        "JWT_SECRET_KEY": "a-private-production-secret",
        "REFRESH_COOKIE_SECURE": "true",
        # The test run sets these in the environment (conftest.py); production refuses them.
        "AUTO_CREATE_SCHEMA": "false",
        "SEED_DEMO_DATA": "false",
        "SEED_DEMO_HISTORY": "false",
    }
    with pytest.raises(ValidationError, match="SMTP_HOST and SMTP_FROM"):
        Settings(_env_file=None, **values)  # type: ignore[call-arg]
    configured = Settings(  # type: ignore[call-arg]
        _env_file=None, SMTP_HOST="smtp.example.com", SMTP_FROM="MacroRep <no-reply@example.com>", **values
    )
    assert configured.smtp_host == "smtp.example.com"
