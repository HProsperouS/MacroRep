"""Uniform handling of request-validation errors, and the HTTP form of the services' errors."""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .exceptions import Conflict, DomainError, Invalid, NotFound, TooMany, Unauthorized, Unavailable

_VALUE_ERROR_PREFIX = "Value error, "
_STATUS: dict[type[DomainError], int] = {
    NotFound: status.HTTP_404_NOT_FOUND,
    Conflict: status.HTTP_409_CONFLICT,
    Invalid: status.HTTP_422_UNPROCESSABLE_CONTENT,
    Unauthorized: status.HTTP_401_UNAUTHORIZED,
    Unavailable: status.HTTP_503_SERVICE_UNAVAILABLE,
    TooMany: status.HTTP_429_TOO_MANY_REQUESTS,
}


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """A service's refusal as its HTTP status, shaped like FastAPI's own errors: ``{"detail": ...}``."""

    assert isinstance(exc, DomainError)
    # The nearest listed class, so a subclass (say, of Conflict) is answered as its parent.
    code = next((_STATUS[cls] for cls in type(exc).__mro__ if cls in _STATUS), status.HTTP_400_BAD_REQUEST)
    headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, TooMany) else None
    return JSONResponse(status_code=code, content={"detail": exc.message}, headers=headers)


def _describe(error: dict[str, Any]) -> str:
    """One readable sentence for an error, e.g. "weightKg: Input should be less than or equal to 400"."""

    message = str(error["msg"]).removeprefix(_VALUE_ERROR_PREFIX)
    # A model-level rule (e.g. calories vs macros) has no single field to name.
    field = next(
        (str(part) for part in reversed(error["loc"]) if isinstance(part, str) and part != "body"), None
    )
    return (
        f"{field}: {message}" if field and not str(error["msg"]).startswith(_VALUE_ERROR_PREFIX) else message
    )


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """422 with each error's location, message and type, but never the rejected input.

    FastAPI's default echoes the offending value back, which (a) crashes on
    NaN or Infinity, since they can't be written as JSON, turning a clean
    rejection into a 500; (b) reflects secrets such as a rejected password;
    and (c) copies oversized inputs straight back into the response.
    ``message`` summarises the first error for display.
    """

    assert isinstance(exc, RequestValidationError)
    errors = [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]} for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"message": _describe(exc.errors()[0]) if errors else "Invalid request", "detail": errors},
    )
