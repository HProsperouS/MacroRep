"""Isolated FastAPI test application, on in-memory SQLite or a throwaway PostgreSQL database.

Set ``TEST_DATABASE_URL`` to a ``postgresql+psycopg://`` database whose name ends in
``_test`` to run the same tests on PostgreSQL instead (CI does). That database's ``public``
schema is wiped before each test.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite://")
ON_POSTGRES = make_url(TEST_DATABASE_URL).get_backend_name() == "postgresql"

# Every test wipes it, so refuse anything that doesn't look like a database kept for tests.
if ON_POSTGRES and not (make_url(TEST_DATABASE_URL).database or "").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must name a database ending in _test: the tests wipe it")

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "LOG_JSON": "false",
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


def _reset_postgres() -> None:
    """Give each test an empty database, as a fresh in-memory SQLite one would be."""

    with psycopg.connect(libpq_conninfo(TEST_DATABASE_URL), autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")


@pytest.fixture
def client() -> Iterator[TestClient]:
    if ON_POSTGRES:
        _reset_postgres()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-Preview-Actor-Id": DEMO_USER_ID, "X-Correlation-ID": "test-run"}
