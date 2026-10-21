"""Isolated FastAPI test application, on a throwaway PostgreSQL database: the database the app
runs on, so the tests see what production does.

By default that's ``macrorep_test`` on the compose PostgreSQL (``docker compose up -d
postgres``), created on first use. ``TEST_DATABASE_URL`` picks another; its name must end in
``_test``, since its ``public`` schema is wiped before each test.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://macrorep:local-development-only@localhost:5432/macrorep_test"
)
_url = make_url(TEST_DATABASE_URL)

if _url.get_backend_name() != "postgresql":
    raise RuntimeError("TEST_DATABASE_URL must be a postgresql+psycopg:// database: tests run on PostgreSQL")
# Every test wipes it, so refuse anything that doesn't look like a database kept for tests.
if not (_url.database or "").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must name a database ending in _test: the tests wipe it")

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "LOG_JSON": "false",
        # No log files from test runs, whatever backend/.env says.
        "LOG_DIR": "",
        "PREVIEW_AUTH_ENABLED": "true",
        "AUTO_CREATE_SCHEMA": "true",
        "SEED_DEMO_DATA": "true",
        # Never a real model, whatever backend/.env says: no API calls, no cost, same answers.
        "COACH_MODEL_PROVIDER": "fake",
    }
)

from app.core.database import libpq_conninfo  # noqa: E402
from app.demo_seed import DEMO_USER_ID  # noqa: E402
from app.main import app  # noqa: E402


def _create_test_database() -> None:
    """Create the test database if it isn't there yet, from the server's ``postgres`` database."""

    server = _url.set(database="postgres").render_as_string(hide_password=False)
    try:
        with psycopg.connect(libpq_conninfo(server), autocommit=True) as connection:
            found = connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_url.database,))
            if found.fetchone() is None:
                connection.execute(f'CREATE DATABASE "{_url.database}"')
    except psycopg.OperationalError as error:
        raise RuntimeError(
            f"Can't reach PostgreSQL at {_url.host}:{_url.port}. "
            "Start it with `docker compose up -d postgres`, or set TEST_DATABASE_URL."
        ) from error


def _reset_database() -> None:
    """Give each test an empty database."""

    with psycopg.connect(libpq_conninfo(TEST_DATABASE_URL), autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")


def pytest_sessionstart(session: pytest.Session) -> None:
    _create_test_database()


@pytest.fixture(autouse=True)
def _fresh_rate_limits() -> None:
    """Each test starts with no sign-in or sign-up attempts counted."""

    from app.shared.rate_limit import limiter, user_limiter

    limiter.reset()
    user_limiter.reset()


@pytest.fixture
def client() -> Iterator[TestClient]:
    _reset_database()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-Preview-Actor-Id": DEMO_USER_ID, "X-Correlation-ID": "test-run"}
