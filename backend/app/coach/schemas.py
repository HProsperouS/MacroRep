"""Coach check-in API contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.shared.schema import CamelModel
from app.shared.validation import MAX_CHAT_LENGTH, MAX_PROPOSAL_VALUE, Identifier, MultilineText

from .models import CheckInStatus, MessageRole, ProposalKind, ProposalStatus


class PipelineStep(CamelModel):
    id: str
    title: str
    detail: str
    status: str


class ProposalChange(CamelModel):
    id: str
    label: str
    unit: str
    before: float
    after: float
    step: float


class Proposal(CamelModel):
    id: str
    kind: ProposalKind
    headline: str
    changes: list[ProposalChange]
    evidence: list[str]
    reviewer_note: str
    status: ProposalStatus


class CheckInStat(CamelModel):
    label: str
    value: str


class CheckIn(CamelModel):
    id: str
    week_label: str
    range_label: str
    status: CheckInStatus
    summary: str
    stats: list[CheckInStat]
    pipeline: list[PipelineStep]
    proposals: list[Proposal]
    suggested_questions: list[str]


class ProposalChangeOverride(CamelModel):
    id: Identifier
    # A user-edited value: never negative (e.g. no negative calorie target).
    after: float = Field(ge=0, le=MAX_PROPOSAL_VALUE)


class ProposalDecisionInput(CamelModel):
    decision: Literal["apply", "reject"]
    changes: list[ProposalChangeOverride] | None = Field(default=None, max_length=20)


class CoachMessage(CamelModel):
    id: str
    role: MessageRole
    text: str


class AskCoachInput(CamelModel):
    text: MultilineText = Field(min_length=1, max_length=MAX_CHAT_LENGTH)
