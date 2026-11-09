"""The coach conversation about one check-in.

Answering turns the user's question into a reply; a question that asks for a
change becomes a revised (or withdrawn) *pending* proposal the user applies on
its card — the chat never changes the week itself, and nothing is written
until the answer exists, so a question interrupted at the model repeats
nothing on retry.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext
from app.shared.exceptions import Unavailable

from .agents.chat import (
    CHAT_HISTORY,
    MAX_CLARIFICATIONS,
    STOP_ASKING,
    answer_question,
    chat_context,
    clarifications_in_a_row,
    proposal_for_chat,
    revise_proposal,
)
from .agents.model import CoachModel
from .models import CheckIn as CheckInModel
from .models import CheckInStatus, MessageRole, ProposalKind, ProposalStatus
from .models import CoachMessage as CoachMessageModel
from .models import Proposal as ProposalModel
from .repository import CoachRepository
from .schemas import CoachMessage

CHAT_UNAVAILABLE = "The coach couldn't answer just now. Please try again."
ALREADY_APPLIED = {
    ProposalKind.NUTRITION: (
        "You've already applied this week's calorie change. To change your target again, edit it on "
        "the Profile page, or start a new check-in after another week of logging."
    ),
    ProposalKind.TRAINING: (
        "You've already applied this week's training change. To change it again, edit the routine on "
        "the Workout plan page, or start a new check-in after another week of logging."
    ),
}
DECIDED_MEANWHILE = "That proposal changed while I was revising it, so I left it as it is."
WITHDRAWN = {
    ProposalKind.NUTRITION: "I've withdrawn this week's calorie change, so your target stays as it is.",
    ProposalKind.TRAINING: "I've withdrawn this week's training change, so your routine stays as it is.",
}
EARLIER_CHECK_IN = (
    "This is an earlier check-in. Ask for changes on your latest one, at the top of the Coach page."
)
NO_SNAPSHOT = (
    "This check-in doesn't have the week's figures saved, so I can't revise it. Start a new one instead."
)
NUTRITION_SKIPPED = "There's too little data this week for a calorie review, so the target stays as it is."


class CoachChat:
    """Answers questions about a check-in, and revises its proposals on request."""

    def __init__(
        self, session: AsyncSession, repository: CoachRepository, model: Callable[[], CoachModel]
    ) -> None:
        self.session = session
        self.repository = repository
        self.model = model

    async def list_messages(self, check_in_id: str) -> list[CoachMessage]:
        return [
            CoachMessage(
                id=message.id,
                role=message.role,
                text=message.text,
                kind="answer" if message.role == MessageRole.USER else message.kind,
            )
            for message in await self.repository.list_messages(check_in_id)
        ]

    async def ask(self, check_in: CheckInModel, text: str, actor: ActorContext) -> CoachMessage:
        """Answer one question about the check-in, from its frozen figures and
        the conversation so far. The question and its answer are stored together,
        only once there is an answer."""

        check_in_id = check_in.id

        snapshot = check_in.input_snapshot or {}
        history = await self.repository.list_messages(check_in_id, latest=CHAT_HISTORY)
        proposals = await self.repository.list_proposals(check_in_id)
        turns = [
            {"role": message.role.value, "text": message.text, "kind": message.kind} for message in history
        ]
        context = chat_context(
            snapshot, check_in.summary, [proposal_for_chat(p) for p in proposals], turns, text
        )
        # Nothing is written before the answer; ending the read transaction now frees its
        # connection for the seconds the model takes.
        await self.session.commit()
        model = self.model()
        answer = await answer_question(model, context, check_in_id)
        if answer is None:
            raise Unavailable(CHAT_UNAVAILABLE)

        kind, reply_text = "answer", answer.reply
        if answer.intent in ("adjust_nutrition", "adjust_workout"):
            if answer.request is None:
                # One question at a time, and not forever: then say how to ask.
                if clarifications_in_a_row(turns) >= MAX_CLARIFICATIONS:
                    reply_text = STOP_ASKING
                else:
                    kind = "clarification"
            else:
                proposal_kind = (
                    ProposalKind.NUTRITION if answer.intent == "adjust_nutrition" else ProposalKind.TRAINING
                )
                kind, reply_text = await self._revise(
                    check_in, snapshot, proposals, proposal_kind, answer.request, model
                )

        for role, message_text in ((MessageRole.USER, text), (MessageRole.COACH, reply_text)):
            reply = await self.repository.add_message(
                CoachMessageModel(
                    check_in_id=check_in_id,
                    owner_id=actor.actor_id,
                    role=role,
                    text=message_text,
                    kind=kind if role == MessageRole.COACH else "answer",
                )
            )
        await self.session.commit()
        return CoachMessage(id=reply.id, role=reply.role, text=reply.text, kind=kind)

    async def _revise(
        self,
        check_in: CheckInModel,
        snapshot: dict[str, object],
        proposals: list[ProposalModel],
        kind: ProposalKind,
        request: str,
        model: CoachModel,
    ) -> tuple[str, str]:
        """Revise this week's proposal of ``kind`` as the user asked: a pending one is replaced
        (its earlier version kept in ``revisions``) or, if they want no change, withdrawn; a
        rejected or missing one gets a new pending proposal; an applied one is left alone.
        Returns the message kind and text."""

        current = await self.repository.get_current(check_in.owner_id)
        if current is None or current.id != check_in.id:
            return "answer", EARLIER_CHECK_IN
        if "target_calories" not in snapshot:
            return "answer", NO_SNAPSHOT
        # A training-only week: the chat can't make the calorie change the check-in held back.
        if kind == ProposalKind.NUTRITION and snapshot.get("nutrition_skipped"):
            return "answer", f"{NUTRITION_SKIPPED} {snapshot['nutrition_skipped']}"
        mine = [proposal for proposal in proposals if proposal.kind == kind]
        if any(proposal.status in (ProposalStatus.APPLIED, ProposalStatus.EDITED) for proposal in mine):
            return "answer", ALREADY_APPLIED[kind]
        live = (ProposalStatus.PENDING, ProposalStatus.APPLIED, ProposalStatus.EDITED)
        others = [proposal for proposal in proposals if proposal.kind != kind and proposal.status in live]
        pending = next((proposal for proposal in mine if proposal.status == ProposalStatus.PENDING), None)

        revision = await revise_proposal(
            model,
            "nutrition" if kind == ProposalKind.NUTRITION else "training",
            snapshot,
            request,
            proposal_for_chat(pending) if pending else None,
            others[0].changes if others else None,
            check_in.id,
        )
        if revision is None:
            raise Unavailable(CHAT_UNAVAILABLE)
        if revision.draft is None and not (revision.withdraw and pending is not None):
            return "answer", revision.message

        # Read again, locked: the user may have decided it, or another revision added one,
        # while the model worked.
        fresh = await self.repository.pending_proposal(check_in.id, kind)
        if (fresh.id if fresh else None) != (pending.id if pending else None):
            return "answer", DECIDED_MEANWHILE
        if revision.draft is None:
            # They want no change: the proposal goes, as if rejected on its card.
            assert fresh is not None
            fresh.status = ProposalStatus.REJECTED
            fresh.decided_utc = datetime.now(UTC)
            return "revision", WITHDRAWN[kind]
        revised = ProposalModel.from_draft(check_in.id, revision.draft)
        if fresh is None:
            await self.repository.add_proposals([revised])
            check_in.status = CheckInStatus.NEEDS_REVIEW
            return "revision", revision.message
        fresh.revisions = [
            *fresh.revisions,
            {
                "headline": fresh.headline,
                "proposed_changes": fresh.proposed_changes,
                "evidence": fresh.evidence,
                "reviewer_note": fresh.reviewer_note,
                "request": request,
                "replaced_utc": datetime.now(UTC).isoformat(),
            },
        ]
        fresh.headline = revised.headline
        fresh.changes = revised.changes
        fresh.proposed_changes = revised.proposed_changes
        fresh.evidence = revised.evidence
        fresh.reviewer_note = revised.reviewer_note
        return "revision", revision.message
