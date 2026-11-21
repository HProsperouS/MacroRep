"""Settings that are refused at start-up rather than failing later."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    "url", ["sqlite+aiosqlite://", "mysql://localhost/macrorep", "postgresql://localhost/x"]
)
def test_the_database_must_be_postgresql_through_psycopg(url: str) -> None:
    with pytest.raises(ValidationError, match="MacroRep runs on PostgreSQL"):
        Settings(_env_file=None, DATABASE_URL=url)  # type: ignore[call-arg]


def test_a_postgresql_url_is_taken() -> None:
    url = "postgresql+psycopg://macrorep:secret@localhost:5432/macrorep"
    assert Settings(_env_file=None, DATABASE_URL=url).database_url == url  # type: ignore[call-arg]


def _production(**values: str) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        DATABASE_URL="postgresql+psycopg://localhost/unused",
        APP_ENV="prod",
        PREVIEW_AUTH_ENABLED="false",
        JWT_SECRET_KEY="a-private-production-secret",
        REFRESH_COOKIE_SECURE="true",
        AUTO_CREATE_SCHEMA="false",
        SEED_DEMO_DATA="false",
        SEED_DEMO_HISTORY="false",
        SMTP_HOST="smtp.example.com",
        SMTP_FROM="MacroRep <no-reply@example.com>",
        **values,
    )


@pytest.mark.parametrize(
    ("settings", "warned"),
    [
        (lambda: _production(), True),
        (lambda: _production(CLIENT_ADDRESS_HEADER="CloudFront-Viewer-Address"), False),
        (lambda: Settings(_env_file=None, DATABASE_URL="postgresql+psycopg://localhost/x"), False),  # type: ignore[call-arg]
    ],
    ids=["production without the header", "production with it", "local"],
)
def test_production_without_the_client_address_header_is_warned_about(
    monkeypatch: pytest.MonkeyPatch, settings: Any, warned: bool
) -> None:
    """Allowed (production needn't sit behind a proxy), but behind CloudFront every user would
    share one address for the sign-in limits."""

    import app.main

    warnings: list[str] = []

    class Logger:
        def warning(self, message: str) -> None:
            warnings.append(message)

    monkeypatch.setattr(app.main, "get_logger", lambda _name=None: Logger())
    app.main.warn_about_settings(settings())
    assert bool(warnings) is warned
    if warned:
        assert "CLIENT_ADDRESS_HEADER" in warnings[0]
