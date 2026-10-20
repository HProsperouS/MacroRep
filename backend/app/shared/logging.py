"""Structured logging and correlation IDs."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Awaitable, Callable, MutableMapping
from contextvars import ContextVar, Token
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, TextIO, cast
from uuid import uuid4

import structlog
from structlog.typing import Processor

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SENSITIVE_KEYS = frozenset({"authorization", "cookie", "password", "secret", "token", "access_token"})
# Days of log files kept, today included.
LOG_RETENTION_DAYS = 14
_LOG_FILE = re.compile(r"^(?P<prefix>.+)-(?P<day>\d{4}-\d{2}-\d{2})\.log$")

ASGIScope = MutableMapping[str, Any]
ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]


def bind_correlation_id(value: str | None = None) -> tuple[str, Token[str | None]]:
    correlation_id = value if value and _SAFE_CORRELATION_ID.fullmatch(value) else str(uuid4())
    token = _correlation_id.set(correlation_id)
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    return correlation_id, token


def reset_correlation_id(token: Token[str | None]) -> None:
    structlog.contextvars.unbind_contextvars("correlation_id")
    _correlation_id.reset(token)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in _SENSITIVE_KEYS else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    return value


def redact_sensitive_fields(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Structlog processor that recursively removes known credential fields."""

    return cast(MutableMapping[str, Any], _redact_value(event_dict))


class DailyFileHandler(logging.StreamHandler[TextIO]):
    """Writes to ``<prefix>-<UTC date>.log`` in ``directory``: a new file each day, and files
    older than ``LOG_RETENTION_DAYS`` are deleted. One process per directory, as in local
    development; several processes writing the same files would interleave their lines.

    The directory and files are created on the first record. A file that can't be written is
    reported on stderr, as logging does, and never fails the code that logged."""

    def __init__(self, directory: Path, prefix: str) -> None:
        super().__init__()
        self.directory = directory
        self.prefix = prefix
        self._day: date | None = None

    def emit(self, record: logging.LogRecord) -> None:
        day = datetime.fromtimestamp(record.created, UTC).date()
        # Forward only: a record from just before midnight that arrives late joins the new file.
        if self._day is None or day > self._day:
            try:
                self._open(day)
            except OSError:
                self.handleError(record)
                return
        super().emit(record)

    def close(self) -> None:
        self.acquire()
        try:
            if self._day is not None:
                self.stream.close()
                self._day = None
        finally:
            self.release()
        super().close()

    def _open(self, day: date) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        stream = (self.directory / f"{self.prefix}-{day.isoformat()}.log").open("a", encoding="utf-8")
        if self._day is not None:
            self.stream.close()
        self.stream, self._day = stream, day
        self._delete_before(day - timedelta(days=LOG_RETENTION_DAYS - 1))

    def _delete_before(self, oldest: date) -> None:
        for path in self.directory.glob(f"{self.prefix}-*.log"):
            match = _LOG_FILE.match(path.name)
            if match is None or match["prefix"] != self.prefix:
                continue
            try:
                day = date.fromisoformat(match["day"])
            except ValueError:
                continue
            if day < oldest:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    continue  # tried again on the next day's file


def configure_logging(*, level: str = "INFO", json_output: bool = True, log_dir: Path | None = None) -> None:
    """Configure stdlib and structlog with one UTC, correlation-aware pipeline.

    With ``log_dir``, every record is also kept in daily JSON-lines files there: ``app-<date>.log``
    for everything at ``level`` and above, ``error-<date>.log`` for errors only.
    """

    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Unknown log level: {level}")

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        # Fields passed as `extra=` to a stdlib logger.
        structlog.stdlib.ExtraAdder(),
        timestamper,
        redact_sensitive_fields,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    def formatter(renderer: Processor) -> logging.Formatter:
        return structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        )

    json_formatter = formatter(structlog.processors.JSONRenderer())
    console_renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(json_formatter if json_output else formatter(console_renderer))
    root = logging.getLogger()
    for old in root.handlers:
        old.close()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    if log_dir is not None:
        for prefix, file_level in (("app", logging.NOTSET), ("error", logging.ERROR)):
            file_handler = DailyFileHandler(log_dir, prefix)
            file_handler.setLevel(file_level)
            file_handler.setFormatter(json_formatter)
            root.addHandler(file_handler)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


class CorrelationIdMiddleware:
    """Bind one safe correlation ID to every HTTP request and response."""

    def __init__(self, app: ASGIApp, *, header_name: str = "X-Correlation-ID") -> None:
        self.app = app
        self.header_name = header_name
        self._header_bytes = header_name.lower().encode("ascii")

    async def __call__(self, scope: ASGIScope, receive: ASGIReceive, send: ASGISend) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        inbound = next(
            (
                value.decode("ascii", errors="ignore")
                for key, value in scope.get("headers", [])
                if key.lower() == self._header_bytes
            ),
            None,
        )
        correlation_id, token = bind_correlation_id(inbound)

        async def send_with_correlation(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != self._header_bytes
                ]
                headers.append((self._header_bytes, correlation_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        except Exception:
            # Logged here, while the request's correlation id is still bound; the server's
            # own report of it goes only to the console.
            get_logger(__name__).exception(
                "unhandled request error", method=scope.get("method"), path=scope.get("path")
            )
            raise
        finally:
            reset_correlation_id(token)
