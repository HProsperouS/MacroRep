"""Why a request was refused, as the services say it: in business terms, never in HTTP.

The web layer turns each into its status code (``app.shared.errors``), so no service
depends on the web framework.
"""

from __future__ import annotations


class DomainError(Exception):
    """A request refused by a business rule. ``message`` is shown to the user."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    """It doesn't exist, or isn't the caller's."""


class Conflict(DomainError):
    """It clashes with the current state: already done, out of date, or changed meanwhile."""


class Invalid(DomainError):
    """The request breaks a rule: past a limit, or not enough data yet."""


class Unauthorized(DomainError):
    """Wrong or missing credentials, or a disabled account."""


class Unavailable(DomainError):
    """Something the request needs (the AI model) couldn't answer just now."""


class TooMany(DomainError):
    """Over a rate limit; ``retry_after`` is the seconds until the next attempt may go through."""

    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after
