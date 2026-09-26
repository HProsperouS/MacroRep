"""Reject NUL bytes in the URL before any route sees them.

Request bodies are covered by the schema types in ``app.shared.validation``,
but path and query values (``/api/foods/{food_id}``, ``?q=``) go straight to
queries as plain strings. Postgres can't store or compare text containing a
NUL byte, so ``/api/foods/abc%00`` would otherwise fail inside the database
driver as a 500. No legitimate URL in this API contains one.
"""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

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
