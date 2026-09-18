"""user password and refresh tokens

Replaces the Cognito subject with the state needed for self-issued auth:
an Argon2 password hash plus the digest and expiry of the current refresh
token (see ``app/auth``).

Revision ID: a1f4c9e2b7d3
Revises: d6e2f5bdaa4f
Create Date: 2026-09-18 14:50:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f4c9e2b7d3"
down_revision: str | None = "d6e2f5bdaa4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("refresh_token_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True))
    # Postgres drops the column's unique constraint along with the column.
    op.drop_column("users", "cognito_subject")


def downgrade() -> None:
    # The original subject values cannot be recovered, so the column comes back
    # nullable rather than restoring the NOT NULL + UNIQUE constraint.
    op.add_column("users", sa.Column("cognito_subject", sa.String(length=255), nullable=True))
    op.drop_column("users", "refresh_expires_at")
    op.drop_column("users", "refresh_token_hash")
    op.drop_column("users", "password_hash")
