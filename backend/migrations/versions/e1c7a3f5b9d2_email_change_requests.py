"""email change requests

A new sign-in email waiting for its code, at most one per user.

Revision ID: e1c7a3f5b9d2
Revises: d3a7c5e1f9b2
Create Date: 2026-11-21 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1c7a3f5b9d2"
down_revision: str | None = "d3a7c5e1f9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_change_requests",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("new_email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_utc", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_email_change_requests_user", "email_change_requests", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_email_change_requests_user", table_name="email_change_requests")
    op.drop_table("email_change_requests")
