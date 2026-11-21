"""Choosing a password: the rules for a new one, changing it signed in, and resetting a forgotten one."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.auth.passwords import check_new_password
from app.core.database import get_session_factory
from app.identity.models import PasswordResetRequest
from tests.fakes import FakeMailer
from tests.helpers import TEST_PASSWORD, login, register

COOKIE = "macrorep_refresh"
CHANGE = "/api/v1/auth/password"
RESET = "/api/v1/auth/password-reset"
CONFIRM_RESET = "/api/v1/auth/password-reset/confirm"
NEW_PASSWORD = "a-brand-new-passphrase"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _new_account(client: TestClient) -> tuple[str, dict[str, str]]:
    email = f"{uuid.uuid4().hex}@example.com"
    registered = register(client, email)
    assert registered.status_code == 201
    return email, _bearer(registered.json()["accessToken"])


def _refresh_with(client: TestClient, refresh_token: str) -> int:
    client.cookies.clear()
    client.cookies.set(COOKIE, refresh_token)
    return client.post("/api/v1/auth/refresh").status_code


def _reset_requests(client: TestClient) -> list[PasswordResetRequest]:
    async def fetch() -> list[PasswordResetRequest]:
        async with get_session_factory()() as session:
            return list(await session.scalars(select(PasswordResetRequest)))

    return client.portal.call(fetch)


# --- Rules for a new password --------------------------------------------------------------


@pytest.mark.parametrize(
    ("password", "reason"),
    [
        ("        ", "only spaces"),
        ("Alex@Example.com", "isn't your email"),
        ("Password1", "too common"),
        ("  qwerty123 ", "too common"),
    ],
)
def test_easy_passwords_are_refused(password: str, reason: str) -> None:
    refused = check_new_password(password, "alex@example.com")
    assert refused is not None and reason in refused


def test_other_passwords_are_taken() -> None:
    assert check_new_password("correct horse battery", "alex@example.com") is None


def test_signing_up_refuses_a_common_password_or_the_email(client: TestClient) -> None:
    common = register(client, "common@example.com", password="password1")
    assert common.status_code == 422
    assert "too common" in common.json()["detail"]
    assert register(client, "same@example.com", password="same@example.com").status_code == 422
    assert register(client, "fine@example.com", password=NEW_PASSWORD).status_code == 201


# --- Changing it, signed in -----------------------------------------------------------------


def test_changing_the_password_signs_out_other_devices(client: TestClient, mailer: FakeMailer) -> None:
    email, headers = _new_account(client)
    other_device = client.cookies.get(COOKIE)
    assert other_device

    changed = client.put(
        CHANGE, headers=headers, json={"currentPassword": TEST_PASSWORD, "newPassword": NEW_PASSWORD}
    )
    assert changed.status_code == 200
    this_device = client.cookies.get(COOKIE)
    assert this_device and this_device != other_device
    assert client.get("/api/v1/users/me", headers=_bearer(changed.json()["accessToken"])).status_code == 200

    assert login(client, email, NEW_PASSWORD).status_code == 200
    assert login(client, email, TEST_PASSWORD).status_code == 401
    assert _refresh_with(client, other_device) == 401
    assert "changed" in mailer.to(email)[-1].subject


def test_changing_needs_the_current_password_and_a_new_usable_one(
    client: TestClient, mailer: FakeMailer
) -> None:
    email, headers = _new_account(client)

    def change(current: str, new: str) -> int:
        return client.put(
            CHANGE, headers=headers, json={"currentPassword": current, "newPassword": new}
        ).status_code

    # 403, not 401: the session is fine, and a 401 would make the client refresh and retry.
    assert change("wrong-password", NEW_PASSWORD) == 403
    assert change(TEST_PASSWORD, TEST_PASSWORD) == 422
    assert change(TEST_PASSWORD, "password123") == 422
    assert change(TEST_PASSWORD, email) == 422
    assert change(TEST_PASSWORD, "short") == 422
    assert (
        client.put(CHANGE, json={"currentPassword": TEST_PASSWORD, "newPassword": NEW_PASSWORD}).status_code
        == 401
    )
    assert login(client, email).status_code == 200
    assert mailer.sent == []


def test_wrong_current_passwords_are_limited_across_email_and_password_changes(
    client: TestClient, mailer: FakeMailer
) -> None:
    _, headers = _new_account(client)
    for _ in range(3):
        body = {"currentPassword": "wrong-password", "newPassword": NEW_PASSWORD}
        assert client.put(CHANGE, headers=headers, json=body).status_code == 403
    for _ in range(2):
        body = {"newEmail": f"{uuid.uuid4().hex}@example.com", "password": "wrong-password"}
        assert client.post("/api/v1/auth/email-change", headers=headers, json=body).status_code == 403

    # Locked now, even with the right password.
    limited = client.put(
        CHANGE, headers=headers, json={"currentPassword": TEST_PASSWORD, "newPassword": NEW_PASSWORD}
    )
    assert limited.status_code == 429
    assert "Too many wrong passwords" in limited.json()["detail"]


def test_right_current_passwords_dont_count_toward_the_limit(client: TestClient, mailer: FakeMailer) -> None:
    _, headers = _new_account(client)
    password = TEST_PASSWORD
    for turn in range(6):
        new = f"{NEW_PASSWORD}-{turn}"
        changed = client.put(CHANGE, headers=headers, json={"currentPassword": password, "newPassword": new})
        assert changed.status_code == 200
        headers, password = _bearer(changed.json()["accessToken"]), new


# --- Resetting a forgotten one --------------------------------------------------------------


def test_a_reset_code_sets_a_new_password_and_signs_in(client: TestClient, mailer: FakeMailer) -> None:
    email, _ = _new_account(client)
    other_device = client.cookies.get(COOKIE)
    assert other_device
    client.cookies.clear()

    assert client.post(RESET, json={"email": f"  {email.upper()} "}).status_code == 202
    assert mailer.sent[-1].to == email
    code = mailer.last_code()

    reset = client.post(CONFIRM_RESET, json={"email": email, "code": code, "newPassword": NEW_PASSWORD})
    assert reset.status_code == 200
    assert client.cookies.get(COOKIE)
    assert (
        client.get("/api/v1/users/me", headers=_bearer(reset.json()["accessToken"])).json()["email"] == email
    )
    assert "reset" in mailer.sent[-1].subject

    assert login(client, email, NEW_PASSWORD).status_code == 200
    assert login(client, email, TEST_PASSWORD).status_code == 401
    assert _refresh_with(client, other_device) == 401
    # The code is spent.
    again = client.post(
        CONFIRM_RESET, json={"email": email, "code": code, "newPassword": "another-passphrase"}
    )
    assert again.status_code == 422


def test_asking_for_a_reset_doesnt_tell_whether_the_email_has_an_account(
    client: TestClient, mailer: FakeMailer
) -> None:
    email, _ = _new_account(client)

    unknown = client.post(RESET, json={"email": "nobody-here@example.com"})
    known = client.post(RESET, json={"email": email})
    assert unknown.status_code == known.status_code == 202
    assert unknown.content == known.content
    assert [sent.to for sent in mailer.sent] == [email]

    refused = client.post(
        CONFIRM_RESET,
        json={"email": "nobody-here@example.com", "code": "123456", "newPassword": NEW_PASSWORD},
    )
    wrong = client.post(CONFIRM_RESET, json={"email": email, "code": "000000", "newPassword": NEW_PASSWORD})
    if mailer.last_code() != "000000":
        assert refused.json() == wrong.json()


def test_five_wrong_reset_codes_end_the_request(client: TestClient, mailer: FakeMailer) -> None:
    email, _ = _new_account(client)
    assert client.post(RESET, json={"email": email}).status_code == 202
    code = mailer.last_code()
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"

    for _ in range(5):
        body = {"email": email, "code": wrong, "newPassword": NEW_PASSWORD}
        assert client.post(CONFIRM_RESET, json=body).status_code == 422
    assert _reset_requests(client) == []
    right = client.post(CONFIRM_RESET, json={"email": email, "code": code, "newPassword": NEW_PASSWORD})
    assert right.status_code == 422
    assert login(client, email).status_code == 200


def test_an_expired_reset_code_is_refused(client: TestClient, mailer: FakeMailer) -> None:
    email, _ = _new_account(client)
    assert client.post(RESET, json={"email": email}).status_code == 202

    async def expire() -> None:
        async with get_session_factory()() as session:
            await session.execute(
                update(PasswordResetRequest).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await session.commit()

    client.portal.call(expire)
    body = {"email": email, "code": mailer.last_code(), "newPassword": NEW_PASSWORD}
    assert client.post(CONFIRM_RESET, json=body).status_code == 422
    assert login(client, email).status_code == 200


def test_a_weak_new_password_doesnt_spend_the_code(client: TestClient, mailer: FakeMailer) -> None:
    email, _ = _new_account(client)
    assert client.post(RESET, json={"email": email}).status_code == 202
    code = mailer.last_code()

    weak = client.post(CONFIRM_RESET, json={"email": email, "code": code, "newPassword": "password123"})
    assert weak.status_code == 422
    assert "too common" in weak.json()["detail"]
    fine = client.post(CONFIRM_RESET, json={"email": email, "code": code, "newPassword": NEW_PASSWORD})
    assert fine.status_code == 200


def test_an_email_change_code_doesnt_reset_the_password(client: TestClient, mailer: FakeMailer) -> None:
    email, headers = _new_account(client)
    body = {"newEmail": f"{uuid.uuid4().hex}@example.com", "password": TEST_PASSWORD}
    assert client.post("/api/v1/auth/email-change", headers=headers, json=body).status_code == 202
    email_change_code = mailer.last_code()
    assert client.post(RESET, json={"email": email}).status_code == 202
    reset_code = mailer.last_code()

    if email_change_code != reset_code:
        body = {"email": email, "code": email_change_code, "newPassword": NEW_PASSWORD}
        assert client.post(CONFIRM_RESET, json=body).status_code == 422
    assert (
        client.post(
            CONFIRM_RESET, json={"email": email, "code": reset_code, "newPassword": NEW_PASSWORD}
        ).status_code
        == 200
    )


def test_a_failed_reset_email_still_answers_the_same(client: TestClient, mailer: FakeMailer) -> None:
    email, _ = _new_account(client)
    mailer.fail = True
    assert client.post(RESET, json={"email": email}).status_code == 202


def test_reset_codes_asked_for_are_limited_per_email(client: TestClient, mailer: FakeMailer) -> None:
    email, _ = _new_account(client)
    for _ in range(5):
        assert client.post(RESET, json={"email": email}).status_code == 202
    limited = client.post(RESET, json={"email": email})
    assert limited.status_code == 429
    assert "Too many reset codes" in limited.json()["detail"]
    assert len(mailer.sent) == 5


def test_reset_codes_tried_are_limited_per_address(client: TestClient, mailer: FakeMailer) -> None:
    body = {"email": "nobody-here@example.com", "code": "123456", "newPassword": NEW_PASSWORD}
    for _ in range(30):
        assert client.post(CONFIRM_RESET, json=body).status_code == 422
    assert client.post(CONFIRM_RESET, json=body).status_code == 429
