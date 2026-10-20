"""Log files: daily JSON lines, a separate error file, retention, and what each line carries."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import REPOSITORY_ROOT, Settings
from app.shared.logging import CorrelationIdMiddleware, DailyFileHandler, configure_logging


@pytest.fixture
def log_dir(tmp_path: Path) -> Iterator[Path]:
    configure_logging(level="INFO", json_output=False, log_dir=tmp_path)
    yield tmp_path
    # Back to the console-only setup the other tests run with.
    configure_logging(level="INFO", json_output=False)


def lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def logged(log_dir: Path, prefix: str) -> list[dict[str, Any]]:
    """The lines of the one file with ``prefix``, named after the day its lines were logged."""

    [path] = log_dir.glob(f"{prefix}-*.log")
    found = lines(path)
    assert all(path.name == f"{prefix}-{line['timestamp'][:10]}.log" for line in found)
    return found


def test_everything_goes_to_the_app_file_and_errors_also_to_the_error_file(log_dir: Path) -> None:
    logger = logging.getLogger("app.test")
    logger.debug("too detailed")
    logger.info("check-in started", extra={"check_in_id": "c1"})
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logger.exception("check-in generation failed")

    app_lines = logged(log_dir, "app")
    assert [line["event"] for line in app_lines] == ["check-in started", "check-in generation failed"]
    assert app_lines[0]["check_in_id"] == "c1"  # extra= fields are kept
    assert app_lines[0]["level"] == "info"

    [error] = logged(log_dir, "error")
    assert error["event"] == "check-in generation failed"
    assert "RuntimeError: boom" in error["exception"]


def test_credentials_are_redacted_in_the_files_too(log_dir: Path) -> None:
    logging.getLogger("app.test").info("login", extra={"password": "hunter2", "email": "a@b.c"})
    [line] = logged(log_dir, "app")
    assert line["password"] == "[REDACTED]"
    assert "hunter2" not in next(log_dir.glob("app-*.log")).read_text()


def test_an_unhandled_request_error_is_logged_with_its_correlation_id(log_dir: Path) -> None:
    app = FastAPI()

    @app.get("/broken")
    async def broken() -> None:
        raise ValueError("bad state")

    app.add_middleware(CorrelationIdMiddleware)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/broken", headers={"X-Correlation-ID": "req-42"}).status_code == 500

    errors = logged(log_dir, "error")
    [error] = [line for line in errors if line["event"] == "unhandled request error"]
    assert (error["correlation_id"], error["method"], error["path"]) == ("req-42", "GET", "/broken")
    assert "ValueError: bad state" in error["exception"]


def record_on(day: date, message: str) -> logging.LogRecord:
    record = logging.makeLogRecord({"msg": message, "levelno": logging.INFO, "levelname": "INFO"})
    record.created = datetime(day.year, day.month, day.day, 12, tzinfo=UTC).timestamp()
    return record


def test_a_new_file_each_day_and_old_ones_deleted(tmp_path: Path) -> None:
    for old in ("app-2026-10-01.log", "app-2026-10-07.log", "error-2026-10-01.log", "notes.log"):
        (tmp_path / old).write_text("old\n")
    handler = DailyFileHandler(tmp_path, "app")
    handler.setFormatter(logging.Formatter("%(message)s"))
    try:
        handler.emit(record_on(date(2026, 10, 19), "monday"))
        handler.emit(record_on(date(2026, 10, 20), "tuesday"))
    finally:
        handler.close()

    assert (tmp_path / "app-2026-10-19.log").read_text() == "monday\n"
    assert (tmp_path / "app-2026-10-20.log").read_text() == "tuesday\n"
    # 14 days kept, today included: 2026-10-07 onwards. Other prefixes and files are left alone.
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "app-2026-10-07.log",
        "app-2026-10-19.log",
        "app-2026-10-20.log",
        "error-2026-10-01.log",
        "notes.log",
    ]


def test_a_late_record_from_before_midnight_joins_the_new_file(tmp_path: Path) -> None:
    handler = DailyFileHandler(tmp_path, "app")
    handler.setFormatter(logging.Formatter("%(message)s"))
    try:
        handler.emit(record_on(date(2026, 10, 20), "after midnight"))
        handler.emit(record_on(date(2026, 10, 19), "just before"))
    finally:
        handler.close()
    assert [path.name for path in tmp_path.iterdir()] == ["app-2026-10-20.log"]
    assert (tmp_path / "app-2026-10-20.log").read_text() == "after midnight\njust before\n"


def test_an_unwritable_log_dir_never_fails_the_caller(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    not_a_dir = tmp_path / "taken"
    not_a_dir.write_text("a file, not a directory")
    configure_logging(level="INFO", json_output=False, log_dir=not_a_dir / "logs")
    try:
        logging.getLogger("app.test").error("still fine")  # must not raise
    finally:
        configure_logging(level="INFO", json_output=False)
    assert "still fine" in capsys.readouterr().out  # the console still gets it


def settings(**values: Any) -> Settings:
    return Settings(_env_file=None, DATABASE_URL="sqlite+aiosqlite://", **values)  # type: ignore[call-arg]


def test_log_dir_is_off_unless_set_and_relative_to_backend(tmp_path: Path) -> None:
    assert settings().log_dir is None
    assert settings(LOG_DIR="").log_dir is None
    assert settings(LOG_DIR="logs").log_dir == REPOSITORY_ROOT / "backend" / "logs"
    assert settings(LOG_DIR=str(tmp_path)).log_dir == tmp_path
