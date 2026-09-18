"""Isolated FastAPI test application backed by in-memory SQLite."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": "sqlite+aiosqlite://",
        "LOG_JSON": "false",
        "PREVIEW_AUTH_ENABLED": "true",
        "AUTO_CREATE_SCHEMA": "true",
        "SEED_DEMO_DATA": "true",
    }
)

from app.demo_seed import DEMO_USER_ID  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-Preview-Actor-Id": DEMO_USER_ID, "X-Correlation-ID": "test-run"}
