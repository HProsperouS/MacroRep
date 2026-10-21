"""Settings that are refused at start-up rather than failing later."""

from __future__ import annotations

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
