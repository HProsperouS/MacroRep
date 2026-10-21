"""Weekly coach check-ins, proposals, and chat messages.

Persistence and API shape only: `pipeline.py` marks the seam where a real
multi-agent generation pipeline plugs in later (see that module's docstring).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence import Base, TimestampMixin

from .pipeline import ProposalDraft


class CheckInStatus(StrEnum):
    # Proposals are being generated in the background; the client polls until it changes.
    RUNNING = "running"
    NEEDS_REVIEW = "needs-review"
    REVIEWED = "reviewed"
    # Generation failed or was interrupted. Nothing was changed; a new check-in can be started.
    FAILED = "failed"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    EDITED = "edited"
    REJECTED = "rejected"


class ProposalKind(StrEnum):
    NUTRITION = "nutrition"
    TRAINING = "training"


class MessageRole(StrEnum):
    USER = "user"
    COACH = "coach"


class CheckIn(TimestampMixin, Base):
    __tablename__ = "coach_check_ins"
    __table_args__ = (
        Index("ix_coach_check_ins_owner_created", "owner_id", "created_utc"),
        # Enforces idempotent creation: a retried POST carrying the same key can
        # never insert a second check-in, even when two requests race. NULL keys
        # (seeded check-ins) are distinct from each other, so they don't collide.
        Index("uq_coach_check_ins_owner_idempotency_key", "owner_id", "idempotency_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    week_label: Mapped[str] = mapped_column(String(64), nullable=False)
    range_label: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[CheckInStatus] = mapped_column(
        SAEnum(CheckInStatus, name="check_in_status"), nullable=False, default=CheckInStatus.NEEDS_REVIEW
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Each item: {"label": str, "value": str}
    stats: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    # Each item: {"id", "title", "detail", "status"}
    pipeline: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    suggested_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # The metrics the proposals were drafted from, frozen at creation so the
    # check-in stays auditable after the underlying logs are edited.
    input_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    # Shown to the user when status is FAILED. Never holds internal error details.
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Proposal(Base):
    __tablename__ = "coach_proposals"
    __table_args__ = (Index("ix_coach_proposals_check_in", "check_in_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    check_in_id: Mapped[str] = mapped_column(
        ForeignKey("coach_check_ins.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ProposalKind] = mapped_column(SAEnum(ProposalKind, name="proposal_kind"), nullable=False)
    headline: Mapped[str] = mapped_column(String(255), nullable=False)
    # Each item: {"id","label","unit","before","after","step"}. The values decided on:
    # the proposal as made, or as the user edited it before applying.
    changes: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    # The changes exactly as proposed, kept unchanged so an edit stays visible in the audit trail.
    proposed_changes: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reviewer_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Earlier versions replaced at the user's request in Coach Chat, oldest first: each with
    # its headline, proposed changes, evidence and reviewer note, the request, and when.
    revisions: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[ProposalStatus] = mapped_column(
        SAEnum(ProposalStatus, name="proposal_status"), nullable=False, default=ProposalStatus.PENDING
    )
    # When the user applied, edited or rejected it; null while pending.
    decided_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def from_draft(cls, check_in_id: str, draft: ProposalDraft) -> Proposal:
        changes = [change.__dict__ for change in draft.changes]
        return cls(
            check_in_id=check_in_id,
            kind=ProposalKind(draft.kind),
            headline=draft.headline,
            changes=changes,
            # Kept apart from `changes`, which an edit later overwrites.
            proposed_changes=[dict(change) for change in changes],
            evidence=draft.evidence,
            reviewer_note=draft.reviewer_note,
        )


class CoachMessage(TimestampMixin, Base):
    __tablename__ = "coach_messages"
    __table_args__ = (Index("ix_coach_messages_check_in_created", "check_in_id", "created_utc"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    check_in_id: Mapped[str] = mapped_column(
        ForeignKey("coach_check_ins.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole, name="message_role"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # For a coach message: an answer, a clarifying question, or the outcome of a revision.
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="answer", server_default="answer")
