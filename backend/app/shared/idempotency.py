"""The ``Idempotency-Key`` header that makes a create safe to retry.

A client sends one key per thing it means to create (a check-in, a finished workout, a
food entry) and the same key on every retry of it. The server stores the key with what it
created, under a unique (owner, key) index, and answers a repeat with that instead of
creating another: so a retry after a lost answer (a timeout, a dropped connection) can't
create a duplicate. Optional where it was added later, so older clients keep working.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

MAX_IDEMPOTENCY_KEY_LENGTH = 255

IdempotencyKey = Annotated[
    str | None, Header(alias="Idempotency-Key", min_length=1, max_length=MAX_IDEMPOTENCY_KEY_LENGTH)
]
