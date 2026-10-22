"""Limits on sign-in and sign-up attempts."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.auth.service import WRONG_CREDENTIALS
from app.core.config import get_settings
from app.main import app
from app.shared import rate_limit
from app.shared.exceptions import Unauthorized
from app.shared.rate_limit import (
    FAILED_LOGINS_PER_EMAIL,
    FAILED_LOGINS_PER_EMAIL_AND_ADDRESS,
    LOGINS_PER_ADDRESS,
    REGISTRATIONS_PER_ADDRESS,
    Limit,
    RateLimiter,
    limiter,
    too_many_message,
)
from tests.helpers import login, register


@pytest.fixture
def elsewhere(client: TestClient) -> Iterator[TestClient]:
    """The same app reached from another address (``client`` connects as "testclient")."""

    with TestClient(app, client=("203.0.113.7", 50000)) as other:
        yield other


def test_five_wrong_passwords_lock_the_account_from_that_address(client: TestClient) -> None:
    register(client, "alex@example.com")
    for _ in range(FAILED_LOGINS_PER_EMAIL_AND_ADDRESS.attempts):
        assert login(client, "alex@example.com", "wrong-password").status_code == 401

    locked = login(client, "Alex@Example.com")  # the same account, however it's written

    assert locked.status_code == 429, "even the right password: guessing can't continue"
    assert locked.json()["detail"] == "Too many attempts. Try again in 15 minutes."
    assert int(locked.headers["Retry-After"]) > 14 * 60
    assert login(client, "other@example.com", "wrong-password").status_code == 401, (
        "other accounts aren't locked"
    )


def test_someone_else_guessing_cant_lock_the_owner_out(client: TestClient, elsewhere: TestClient) -> None:
    register(client, "alex@example.com")
    for _ in range(FAILED_LOGINS_PER_EMAIL_AND_ADDRESS.attempts + 1):
        login(elsewhere, "alex@example.com", "wrong-password")

    assert login(client, "alex@example.com").status_code == 200


def test_guessing_one_account_from_many_addresses_is_bounded(client: TestClient) -> None:
    register(client, "alex@example.com")
    for index in range(FAILED_LOGINS_PER_EMAIL.attempts):
        with TestClient(app, client=(f"198.51.100.{index}", 50000)) as guesser:
            assert login(guesser, "alex@example.com", "wrong-password").status_code == 401

    with TestClient(app, client=("198.51.100.250", 50000)) as fresh_address:
        assert login(fresh_address, "alex@example.com", "wrong-password").status_code == 429


def test_a_successful_sign_in_forgets_earlier_wrong_passwords_from_there(client: TestClient) -> None:
    register(client, "alex@example.com")
    for _ in range(FAILED_LOGINS_PER_EMAIL_AND_ADDRESS.attempts - 1):
        login(client, "alex@example.com", "wrong-password")
    assert login(client, "alex@example.com").status_code == 200

    for _ in range(FAILED_LOGINS_PER_EMAIL_AND_ADDRESS.attempts - 1):
        assert login(client, "alex@example.com", "wrong-password").status_code == 401
    assert login(client, "alex@example.com").status_code == 200


def test_only_wrong_passwords_count_against_the_account(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(client, "alex@example.com")

    async def broken(*_: object) -> None:
        raise RuntimeError("database down")

    monkeypatch.setattr("app.auth.service.AuthService.login", broken)
    failing = TestClient(app, raise_server_exceptions=False)
    for _ in range(FAILED_LOGINS_PER_EMAIL_AND_ADDRESS.attempts + 1):
        assert login(failing, "alex@example.com").status_code == 500
    monkeypatch.undo()

    assert login(client, "alex@example.com").status_code == 200


def test_attempts_are_counted_before_the_password_is_checked(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """So guesses sent at the same moment can't all pass the check while none is counted yet."""

    counted: list[int] = []

    async def checking(*_: object) -> None:
        counted.append(len(limiter._hits.get(("login-failed", "alex@example.com from testclient"), ())))  # noqa: SLF001
        raise Unauthorized(WRONG_CREDENTIALS)

    monkeypatch.setattr("app.auth.service.AuthService.login", checking)
    login(client, "alex@example.com", "wrong-password")
    assert counted == [1]


def test_one_address_can_only_try_so_many_accounts(client: TestClient) -> None:
    for index in range(LOGINS_PER_ADDRESS.attempts):
        assert login(client, f"guess-{index}@example.com", "wrong-password").status_code == 401

    assert login(client, "someone-else@example.com", "wrong-password").status_code == 429


def test_one_address_can_only_sign_up_so_often_refused_attempts_included(client: TestClient) -> None:
    assert register(client, "taken@example.com").status_code == 201
    for _ in range(REGISTRATIONS_PER_ADDRESS.attempts - 1):
        assert register(client, "taken@example.com").status_code == 409

    refused = register(client, "new@example.com")
    assert refused.status_code == 429
    assert refused.headers["Retry-After"]


def test_switched_off_nothing_is_counted(client: TestClient) -> None:
    settings = get_settings().model_copy(update={"rate_limits_enabled": False})
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        for _ in range(FAILED_LOGINS_PER_EMAIL_AND_ADDRESS.attempts + 1):
            assert login(client, "alex@example.com", "wrong-password").status_code == 401
        assert register(client, "alex@example.com").status_code == 201
    finally:
        app.dependency_overrides.pop(get_settings)
    assert limiter._hits == {}  # noqa: SLF001


def test_attempts_age_out_of_the_window() -> None:
    now = [0.0]
    window = RateLimiter(clock=lambda: now[0])
    limit = Limit(attempts=2, window_seconds=60)
    key = ("login", "1.2.3.4")

    window.hit(key, limit)
    now[0] = 30
    window.hit(key, limit)
    assert window.retry_after(key, limit) == 30, "until the first attempt is a minute old"
    now[0] = 60
    assert window.retry_after(key, limit) is None


def test_memory_stays_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "_MAX_KEYS", 3)
    bounded = RateLimiter(clock=lambda: 0.0)
    limit = Limit(attempts=5, window_seconds=60)

    assert bounded.retry_after(("login", "never-seen"), limit) is None
    assert bounded._hits == {}, "checking records nothing"  # noqa: SLF001
    for index in range(5):
        bounded.hit(("login", f"10.0.0.{index}"), limit)
    assert list(bounded._hits) == [("login", "10.0.0.2"), ("login", "10.0.0.3"), ("login", "10.0.0.4")]  # noqa: SLF001


def test_the_wait_is_given_in_whole_minutes_then_hours() -> None:
    assert too_many_message(30) == "Too many attempts. Try again in 1 minute."
    assert too_many_message(61) == "Too many attempts. Try again in 2 minutes."
    assert too_many_message(60 * 60 + 1) == "Too many attempts. Try again in 61 minutes."
    assert too_many_message(2 * 60 * 60) == "Too many attempts. Try again in 120 minutes."
    assert too_many_message(2 * 60 * 60 + 1) == "Too many attempts. Try again in 3 hours."
    assert too_many_message(24 * 60 * 60) == "Too many attempts. Try again in 24 hours."
