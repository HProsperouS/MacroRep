"""Isolated FastAPI test application, on a throwaway PostgreSQL database: the database the app
runs on, so the tests see what production does.

By default that's ``macrorep_test`` on the compose PostgreSQL (``docker compose up -d
postgres``), created on first use. ``TEST_DATABASE_URL`` picks another; its name must end in
``_test``, since its ``public`` schema is wiped before each test.

Run in parallel (``pytest -n auto``), each worker gets a database of its own beside it
(``macrorep_gw0_test``, ...), so no worker wipes another's.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

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
# pytest-xdist names each worker (gw0, gw1, ...).
if worker := os.environ.get("PYTEST_XDIST_WORKER"):
    _url = _url.set(database=f"{(_url.database or '').removesuffix('_test')}_{worker}_test")
    TEST_DATABASE_URL = _url.render_as_string(hide_password=False)

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
        "SEED_DEMO_HISTORY": "false",
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


async def _add_a_finished_check_in() -> None:
    """A week a little off the goal rate, so the coach tests have a proposal to work with."""

    from app.coach.agents.fake_model import FakeCoachModel
    from app.coach.agents.graph import run_agents
    from app.coach.models import CheckIn, Proposal
    from app.core.database import get_session_factory

    snapshot: dict[str, object] = {
        "avg_calories": 2410,
        "target_calories": 2350,
        "target_version": None,
        "adherence_percent": 85,
        "complete_days": 6,
        "partial_days": 0,
        "missing_days": 0,
        "target_gap_kcal": 360,
        "workouts_done": 3,
        "workouts_planned": 3,
        "completion_percent": 100.0,
        "avg_rpe": 8.0,
        "weight_change_kg": -0.3,
        "goal_rate_kg_per_week": -0.5,
        "goal": "lose",
        "routines": [],
        "exercise_trends": {},
    }
    draft = await run_agents(snapshot, FakeCoachModel())
    today = datetime.now(UTC).date()
    async with get_session_factory()() as session:
        check_in = CheckIn(
            owner_id=DEMO_USER_ID,
            week_label="Week 1",
            range_label=f"{(today - timedelta(days=6)).isoformat()} – {today.isoformat()}",
            summary=draft.summary,
            stats=draft.stats,
            pipeline=draft.pipeline,
            suggested_questions=draft.suggested_questions,
            input_snapshot=snapshot,
        )
        session.add(check_in)
        await session.flush()
        session.add_all(Proposal.from_draft(check_in.id, proposal) for proposal in draft.proposals)
        await session.commit()


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
        test_client.portal.call(_add_a_finished_check_in)
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-Preview-Actor-Id": DEMO_USER_ID, "X-Correlation-ID": "test-run"}
