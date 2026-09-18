"""Weekly coach check-ins, proposals, and chat messages.

Persistence and API shape only: `pipeline.py` marks the seam where a real
multi-agent generation pipeline plugs in later (see that module's docstring).
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence import Base, TimestampMixin


class CheckInStatus(StrEnum):
    NEEDS_REVIEW = "needs-review"
    REVIEWED = "reviewed"


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
    __table_args__ = (Index("ix_coach_check_ins_owner_created", "owner_id", "created_utc"),)

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


class Proposal(Base):
    __tablename__ = "coach_proposals"
    __table_args__ = (Index("ix_coach_proposals_check_in", "check_in_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uuid.uuid4().hex)
    check_in_id: Mapped[str] = mapped_column(
        ForeignKey("coach_check_ins.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ProposalKind] = mapped_column(SAEnum(ProposalKind, name="proposal_kind"), nullable=False)
    headline: Mapped[str] = mapped_column(String(255), nullable=False)
    # Each item: {"id","label","unit","before","after","step"}
    changes: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reviewer_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[ProposalStatus] = mapped_column(
        SAEnum(ProposalStatus, name="proposal_status"), nullable=False, default=ProposalStatus.PENDING
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
