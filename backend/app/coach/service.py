"""Check-in retrieval, proposal decisions, and coach chat."""

from __future__ import annotations

from typing import cast

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext

from .models import CoachMessage as CoachMessageModel
from .models import MessageRole, ProposalStatus
from .models import Proposal as ProposalModel
from .repository import CoachRepository
from .schemas import (
    CheckIn,
    CheckInStat,
    CoachMessage,
    PipelineStep,
    Proposal,
    ProposalChange,
    ProposalDecisionInput,
)


def _to_proposal_read(proposal: ProposalModel) -> Proposal:
    return Proposal(
        id=proposal.id,
        kind=proposal.kind,
        headline=proposal.headline,
        changes=[ProposalChange(**change) for change in proposal.changes],
        evidence=list(proposal.evidence),
        reviewer_note=proposal.reviewer_note,
        status=proposal.status,
    )


class CoachService:
    def __init__(self, session: AsyncSession, repository: CoachRepository) -> None:
        self.session = session
        self.repository = repository

    async def get_current(self, actor: ActorContext) -> CheckIn | None:
        check_in = await self.repository.get_current(actor.actor_id)
        if check_in is None:
            return None
        proposals = await self.repository.list_proposals(check_in.id)
        return CheckIn(
            id=check_in.id,
            week_label=check_in.week_label,
            range_label=check_in.range_label,
            status=check_in.status,
            summary=check_in.summary,
            stats=[CheckInStat(**stat) for stat in check_in.stats],
            pipeline=[PipelineStep(**step) for step in check_in.pipeline],
            proposals=[_to_proposal_read(proposal) for proposal in proposals],
            suggested_questions=list(check_in.suggested_questions),
        )

    async def decide_proposal(
        self, check_in_id: str, proposal_id: str, payload: ProposalDecisionInput, actor: ActorContext
    ) -> Proposal:
        check_in = await self.repository.get_owned(check_in_id, actor.actor_id)
        if check_in is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Check-in not found")
        proposal = await self.repository.get_proposal(proposal_id, check_in_id)
        if proposal is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
        if proposal.status != ProposalStatus.PENDING:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"Proposal has already been decided ({proposal.status.value})"
            )

        if payload.decision == "reject":
            proposal.status = ProposalStatus.REJECTED
        elif payload.decision == "apply":
            if payload.changes:
                overrides = {override.id: override.after for override in payload.changes}
                proposal.changes = [
                    {**change, "after": overrides.get(cast(str, change["id"]), change["after"])}
                    for change in proposal.changes
                ]
                proposal.status = ProposalStatus.EDITED
            else:
                proposal.status = ProposalStatus.APPLIED
        else:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "decision must be 'apply' or 'reject'")

        await self.session.commit()
        await self.session.refresh(proposal)
        return _to_proposal_read(proposal)

    async def ask_coach(self, check_in_id: str, text: str, actor: ActorContext) -> CoachMessage:
        check_in = await self.repository.get_owned(check_in_id, actor.actor_id)
        if check_in is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Check-in not found")

        await self.repository.add_message(
            CoachMessageModel(
                check_in_id=check_in_id, owner_id=actor.actor_id, role=MessageRole.USER, text=text
            )
        )
        # Placeholder reply — see app/coach/pipeline.py for why this isn't a real LLM call yet.
        reply = await self.repository.add_message(
            CoachMessageModel(
                check_in_id=check_in_id,
                owner_id=actor.actor_id,
                role=MessageRole.COACH,
                text=(
                    "Thanks for the question — the full coaching pipeline isn't wired up yet, "
                    "so I can't answer that in detail."
                ),
            )
        )
        await self.session.commit()
        return CoachMessage(id=reply.id, role=reply.role, text=reply.text)
