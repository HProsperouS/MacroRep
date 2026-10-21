"""Slowing down password guessing and bulk sign-ups (plan.md §17).

Counts live in this process's memory, which is enough for one server and for local
development. Several servers behind a load balancer would each count on their own, so
there the limits belong in a shared store or at the edge (see docs/deployment.md).
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Limit:
    attempts: int
    window_seconds: float


# Wrong passwords for one account from one address: stops guessing it, and someone else
# entering wrong passwords elsewhere can't lock its owner out.
FAILED_LOGINS_PER_EMAIL_AND_ADDRESS = Limit(5, 15 * 60)
# Wrong passwords for one account from anywhere: bounds guessing spread over many
# addresses, high enough that locking the owner out takes a sustained attack.
FAILED_LOGINS_PER_EMAIL = Limit(50, 60 * 60)
# Every sign-in from one address, right or wrong: stops guessing across many accounts.
LOGINS_PER_ADDRESS = Limit(30, 15 * 60)
# Sign-ups from one address, including refused ones: "already registered" tells whether
# an email has an account, so this also slows checking addresses in bulk.
REGISTRATIONS_PER_ADDRESS = Limit(10, 60 * 60)

# Memory stays bounded: expired keys are swept at most once a minute, and past the cap the
# oldest keys are dropped (forgetting some attempts is better than running out of memory).
_MAX_KEYS = 100_000
_SWEEP_EVERY_SECONDS = 60
_LONGEST_WINDOW = max(
    limit.window_seconds
    for limit in (
        FAILED_LOGINS_PER_EMAIL_AND_ADDRESS,
        FAILED_LOGINS_PER_EMAIL,
        LOGINS_PER_ADDRESS,
        REGISTRATIONS_PER_ADDRESS,
    )
)


class RateLimiter:
    """Sliding-window counts per key."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._swept_at = clock()

    def retry_after(self, key: tuple[str, str], limit: Limit) -> int | None:
        """Seconds until ``key`` may try again, or None if it may now. Records nothing."""

        hits = self._hits.get(key)
        if hits is None:
            return None
        self._expire(hits, limit)
        if len(hits) < limit.attempts:
            return None
        return max(1, math.ceil(hits[0] + limit.window_seconds - self._clock()))

    def hit(self, key: tuple[str, str], limit: Limit) -> None:
        hits = self._hits.setdefault(key, deque())
        self._expire(hits, limit)
        hits.append(self._clock())
        self._keep_bounded()

    def undo(self, key: tuple[str, str]) -> None:
        """Take back the latest hit, e.g. an attempt counted in advance that didn't happen."""

        hits = self._hits.get(key)
        if hits:
            hits.pop()

    def clear(self, key: tuple[str, str]) -> None:
        self._hits.pop(key, None)

    def reset(self) -> None:
        self._hits.clear()

    def _expire(self, hits: deque[float], limit: Limit) -> None:
        cutoff = self._clock() - limit.window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()

    def _keep_bounded(self) -> None:
        now = self._clock()
        if now - self._swept_at >= _SWEEP_EVERY_SECONDS:
            self._swept_at = now
            cutoff = now - _LONGEST_WINDOW
            for key in [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]:
                del self._hits[key]
        while len(self._hits) > _MAX_KEYS:
            del self._hits[next(iter(self._hits))]  # the oldest key


limiter = RateLimiter()


def too_many_message(seconds: int) -> str:
    minutes = math.ceil(seconds / 60)
    return f"Too many attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}."
