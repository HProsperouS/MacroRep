"""password reset requests

A forgotten password waiting for its emailed code, at most one per user.

Revision ID: f2d8b4a6c0e3
Revises: e1c7a3f5b9d2
Create Date: 2026-11-21 14:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2d8b4a6c0e3"
down_revision: str | None = "e1c7a3f5b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_requests",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_utc", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_password_reset_requests_user", "password_reset_requests", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_password_reset_requests_user", table_name="password_reset_requests")
    op.drop_table("password_reset_requests")
