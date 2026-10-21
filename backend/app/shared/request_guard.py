"""Reject NUL bytes in the URL before any route sees them.

Request bodies are covered by the schema types in ``app.shared.validation``,
but path and query values (``/api/foods/{food_id}``, ``?q=``) go straight to
queries as plain strings. Postgres can't store or compare text containing a
NUL byte, so ``/api/foods/abc%00`` would otherwise fail inside the database
driver as a 500. No legitimate URL in this API contains one.
"""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_MESSAGE = "The URL contains a NUL character"


class RejectNulBytesMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and _has_nul(scope):
            response = JSONResponse({"message": _MESSAGE, "detail": _MESSAGE}, status_code=400)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _has_nul(scope: Scope) -> bool:
    # `path` is already percent-decoded; the query string is still raw bytes.
    query = bytes(scope.get("query_string", b"")).lower()
    return "\x00" in scope["path"] or b"%00" in query or b"\x00" in query


# The largest body any route needs: a 4 MB meal photo as base64 in JSON (app/food/photo.py).
MAX_BODY_BYTES = 6 * 1024 * 1024
_TOO_LARGE = "The request is too large"


class _BodyTooLarge(Exception):
    pass


class LimitBodySizeMiddleware:
    """Refuse a body over ``MAX_BODY_BYTES`` with 413 before it is all read: by its declared
    length up front, or, for a body sent without one, as soon as it passes the limit."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope.get("headers", [])).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            await _refuse(scope, receive, send)
            return

        received = 0
        started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_BODY_BYTES:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLarge:
            if started:
                raise
            await _refuse(scope, receive, send)


async def _refuse(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse({"message": _TOO_LARGE, "detail": _TOO_LARGE}, status_code=413)
    await response(scope, receive, send)
