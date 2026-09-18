"""Coach check-in API contracts."""

from __future__ import annotations

from pydantic import Field

from app.shared.schema import CamelModel

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
    id: str
    after: float


class ProposalDecisionInput(CamelModel):
    decision: str
    changes: list[ProposalChangeOverride] | None = None


class CoachMessage(CamelModel):
    id: str
    role: MessageRole
    text: str


class AskCoachInput(CamelModel):
    text: str = Field(min_length=1)
