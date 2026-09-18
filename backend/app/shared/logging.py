"""Structured logging and correlation IDs."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Awaitable, Callable, MutableMapping
from contextvars import ContextVar, Token
from typing import Any, cast
from uuid import uuid4

import structlog
from structlog.typing import Processor

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SENSITIVE_KEYS = frozenset({"authorization", "cookie", "password", "secret", "token", "access_token"})

ASGIScope = MutableMapping[str, Any]
ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]


def get_correlation_id() -> str | None:
    return _correlation_id.get()


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


def configure_logging(*, level: str = "INFO", json_output: bool = True) -> None:
    """Configure stdlib and structlog with one UTC, correlation-aware pipeline."""

    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Unknown log level: {level}")

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        redact_sensitive_fields,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

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
        finally:
            reset_correlation_id(token)
