"""user sessions

One session per signed-in device, instead of one refresh token per user: signing in on a
second device no longer signs the first out. Each user's live token becomes their first
session, so nobody is signed out by the upgrade.

The old ``users.refresh_token_hash`` and ``refresh_expires_at`` columns are kept, unused by
this release: the previous release's tasks still read them while a deploy replaces them, so
dropping them here would fail every signed-in request in that window. A later release drops
them (docs/follow-ups.md).

Revision ID: b4f0d6c2e8a5
Revises: a3e9c5b1d7f4
Create Date: 2026-11-21 20:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4f0d6c2e8a5"
down_revision: str | None = "a3e9c5b1d7f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_utc", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_user_sessions_refresh_token_hash", "user_sessions", ["refresh_token_hash"], unique=True
    )
    op.create_index("ix_user_sessions_user_last_used", "user_sessions", ["user_id", "last_used_utc"])
    op.execute(
        """
        INSERT INTO user_sessions (id, user_id, refresh_token_hash, expires_at, last_used_utc, created_utc)
        SELECT replace(gen_random_uuid()::text, '-', ''), id, refresh_token_hash, refresh_expires_at,
               now(), now()
        FROM users
        WHERE refresh_token_hash IS NOT NULL AND refresh_expires_at IS NOT NULL
        """
    )


def downgrade() -> None:
    # Back to one token per user: each keeps their most recently used device signed in.
    op.execute(
        """
        UPDATE users
        SET refresh_token_hash = latest.refresh_token_hash, refresh_expires_at = latest.expires_at
        FROM (
            SELECT DISTINCT ON (user_id) user_id, refresh_token_hash, expires_at
            FROM user_sessions
            ORDER BY user_id, last_used_utc DESC
        ) AS latest
        WHERE users.id = latest.user_id
        """
    )
    op.drop_index("ix_user_sessions_user_last_used", table_name="user_sessions")
    op.drop_index("uq_user_sessions_refresh_token_hash", table_name="user_sessions")
    op.drop_table("user_sessions")
