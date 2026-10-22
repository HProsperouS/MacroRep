"""Check-in creation and retrieval, proposal decisions, and coach chat."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.identity.dependencies import ActorContext
from app.profile.repository import ProfileRepository
from app.profile.service import zone_of
from app.shared.exceptions import Conflict, Invalid, NotFound, Unavailable
from app.shared.rate_limit import (
    CHAT_QUESTIONS_PER_USER,
    CHECK_INS_PER_USER,
    count_attempt,
    counted_attempt,
    user_limiter,
)
from app.shared.timezones import local_today

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
from .agents.graph import run_agents
from .agents.metrics import RunMetrics, RunOutcome, elapsed_ms
from .agents.model import CoachModel
from .apply import ROUTINE_CHANGED, ProposalApplier
from .models import CheckIn as CheckInModel
from .models import CheckInStatus, MessageRole, ProposalKind, ProposalStatus
from .models import CoachMessage as CoachMessageModel
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
from .snapshot import CHECK_IN_WINDOW_DAYS, WeekSnapshot


def _to_proposal_read(proposal: ProposalModel) -> Proposal:
    return Proposal(
        id=proposal.id,
        kind=proposal.kind,
        headline=proposal.headline,
        changes=[ProposalChange(**change) for change in proposal.changes],
        evidence=list(proposal.evidence),
        reviewer_note=proposal.reviewer_note,
        status=proposal.status,
        proposed_changes=[ProposalChange(**change) for change in proposal.proposed_changes],
        decided_at=proposal.decided_utc,
    )


# A run that hasn't finished by then is abandoned and marked failed.
RUN_TIMEOUT_SECONDS = 120
# A check-in still RUNNING this long after it started was lost (e.g. a restart mid-run).
STALE_RUN_AFTER = timedelta(minutes=10)
FAILED_REASON = (
    "Something went wrong while preparing this check-in. Nothing was changed; start a new one to try again."
)
CHAT_NOT_READY = "Questions open once the check-in is ready."
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
INTERRUPTED_REASON = (
    "This check-in was interrupted before it finished. Nothing was changed; start a new one to try again."
)
RUNNING_PIPELINE: list[dict[str, str]] = [
    {
        "id": "gather",
        "title": "Gather week's data",
        "detail": "Food log, workouts, weigh-ins.",
        "status": "done",
    },
    {"id": "propose", "title": "Draft proposals", "detail": "Reviewing your week…", "status": "running"},
]

logger = logging.getLogger(__name__)


def _check_in_count(owner_id: str) -> tuple[str, str]:
    return ("check_in", owner_id)


def _failed_pipeline(steps: list[dict[str, str]]) -> list[dict[str, str]]:
    """The steps as they stood, with the one that was running marked failed."""

    return [{**step, "status": "failed"} if step["status"] == "running" else step for step in steps]


class CoachService:
    def __init__(
        self,
        session: AsyncSession,
        repository: CoachRepository,
        profiles: ProfileRepository,
        week: WeekSnapshot,
        applier: ProposalApplier,
        model: Callable[[], CoachModel],
        checkpointer: Callable[[], BaseCheckpointSaver[str]],
        *,
        rate_limits: bool,
    ) -> None:
        """``model`` and ``checkpointer`` are called when needed, so a misconfigured model fails
        that run, and a run uses the checkpointer current then. With ``rate_limits``, each user
        gets ``CHECK_INS_PER_USER`` check-ins and ``CHAT_QUESTIONS_PER_USER`` questions (then 429);
        one that fails on our side gives its count back."""

        self.session = session
        self.repository = repository
        self.profiles = profiles
        self.week = week
        self.applier = applier
        self.model = model
        self.checkpointer = checkpointer
        self.rate_limits = rate_limits

    async def _forget_run(self, check_in_id: str) -> None:
        """Drop a finished run's checkpoints: the check-in row holds the outcome, and nothing
        resumes a run that ended, so keeping them would only grow the store."""

        try:
            await self.checkpointer().adelete_thread(check_in_id)
        except Exception:
            logger.warning("couldn't delete check-in checkpoints", extra={"check_in_id": check_in_id})

    async def get_current(self, actor: ActorContext) -> CheckIn | None:
        check_in = await self.repository.get_current(actor.actor_id)
        if check_in is None:
            return None
        await self._fail_if_stale(check_in)
        return await self._to_read(check_in)

    async def _fail_if_stale(self, check_in: CheckInModel) -> None:
        """A run still RUNNING long after it began was lost (e.g. the server restarted
        mid-run): mark it failed so the user can start another."""

        if check_in.status != CheckInStatus.RUNNING:
            return
        if datetime.now(UTC) - check_in.created_utc < STALE_RUN_AFTER:
            return
        await self._mark_failed(check_in.id, check_in.pipeline, INTERRUPTED_REASON)
        await self.session.refresh(check_in)

    async def _mark_failed(self, check_in_id: str, steps: list[dict[str, str]], reason: str) -> None:
        """Mark a RUNNING check-in failed, and drop its checkpoints: a failed run is never
        resumed. Does nothing if it already moved on, e.g. finished meanwhile."""

        if await self.repository.finish_run(
            check_in_id, status=CheckInStatus.FAILED, failure_reason=reason, pipeline=_failed_pipeline(steps)
        ):
            await self.session.commit()
            await self._forget_run(check_in_id)

    async def start_check_in(self, idempotency_key: str, actor: ActorContext) -> tuple[CheckIn, bool]:
        """Create a check-in for the last 7 days; returns it and whether it was newly created.

        Idempotent per (user, key): replaying a key returns the check-in it
        originally created instead of generating another one. Only a
        successful creation consumes a key, so a request refused for missing
        data can be retried with the same key once the data is logged.
        """

        existing = await self.repository.get_by_idempotency_key(actor.actor_id, idempotency_key)
        if existing is not None:
            await self._fail_if_stale(existing)
            return await self._to_read(existing), False

        current = await self.repository.get_current(actor.actor_id)
        if current is not None:
            await self._fail_if_stale(current)
            if current.status == CheckInStatus.RUNNING:
                raise Conflict("Your check-in is still being prepared. It'll be ready shortly.")
            if any(
                proposal.status == ProposalStatus.PENDING
                for proposal in await self.repository.list_proposals(current.id)
            ):
                raise Conflict(
                    "Your current check-in still has proposals to review. Apply or reject them first.",
                )

        profile = await self.profiles.get(actor.actor_id)
        zone = zone_of(profile)
        today = local_today(zone)
        start = today - timedelta(days=CHECK_IN_WINDOW_DAYS - 1)
        # Checked and frozen now, so a lack of data is refused at once and the proposals,
        # generated afterwards in the background, rest on exactly these numbers.
        snapshot = await self.week.gather(actor.actor_id, profile, start, today, zone)
        # Counted before the row is written, so starts sent at once can't all slip under the
        # limit, and given back unless the row is written: then no run, and no model calls.
        count_key = _check_in_count(actor.actor_id)
        if self.rate_limits:
            count_attempt(
                (count_key, CHECK_INS_PER_USER),
                reason="That's a lot of check-ins for today.",
                counts=user_limiter,
            )
        created = False
        try:
            check_in = CheckInModel(
                owner_id=actor.actor_id,
                week_label=f"Week {await self.repository.count_for_owner(actor.actor_id) + 1}",
                range_label=f"{start.isoformat()} – {today.isoformat()}",
                status=CheckInStatus.RUNNING,
                summary="Reviewing your week…",
                stats=[],
                pipeline=RUNNING_PIPELINE,
                suggested_questions=[],
                idempotency_key=idempotency_key,
                input_snapshot=snapshot,
            )
            try:
                await self.repository.add_check_in(check_in)
            except IntegrityError:
                # Lost a race with a concurrent request carrying the same key (e.g.
                # a double-submit): the unique (owner_id, idempotency_key) index
                # rejected this insert. The winner's row is committed or about to
                # be, so answer with it — exactly what a sequential replay gets.
                await self.session.rollback()
                winner = await self.repository.get_by_idempotency_key(actor.actor_id, idempotency_key)
                if winner is None:
                    raise
                return await self._to_read(winner), False
            await self.session.commit()
            created = True
        finally:
            if self.rate_limits and not created:
                user_limiter.undo(count_key)
        return await self._to_read(check_in), True

    async def generate(self, check_in_id: str) -> None:
        """Draft the proposals for a RUNNING check-in from its frozen snapshot.

        Runs in the background after ``start_check_in`` has answered. Every write is
        conditional on the check-in still being RUNNING, so a duplicate run, or one that
        outlived the stale sweep, changes nothing. Any error marks the check-in FAILED
        with a user-facing reason; the user's plan is never touched here, only proposals
        are written.
        """

        check_in = await self.repository.get(check_in_id)
        if check_in is None:
            return
        # A run resumed long after it began (e.g. after a long outage) is failed, not finished late.
        await self._fail_if_stale(check_in)
        if check_in.status != CheckInStatus.RUNNING:
            return
        steps, snapshot = check_in.pipeline, check_in.input_snapshot or {}
        metrics = RunMetrics(model="unknown")
        outcome: RunOutcome = "failed"
        error_name: str | None = None
        started = time.monotonic()
        try:
            model = self.model()
            metrics.model = model.name
            draft = await asyncio.wait_for(
                run_agents(
                    snapshot,
                    model,
                    thread_id=check_in_id,
                    checkpointer=self.checkpointer(),
                    metrics=metrics,
                ),
                timeout=RUN_TIMEOUT_SECONDS,
            )
            stored = await self.repository.finish_run(
                check_in_id,
                status=CheckInStatus.NEEDS_REVIEW if draft.proposals else CheckInStatus.REVIEWED,
                summary=draft.summary,
                stats=draft.stats,
                pipeline=draft.pipeline,
                suggested_questions=draft.suggested_questions,
            )
            if stored:
                await self.repository.add_proposals(
                    [ProposalModel.from_draft(check_in_id, proposal) for proposal in draft.proposals]
                )
                await self.session.commit()
            # Otherwise it was already marked failed (or finished) while this run was drafting.
            outcome = "completed" if stored else "discarded"
        except Exception as error:
            # Not asyncio.CancelledError (a BaseException): a run stopped at shutdown stays
            # RUNNING, with its checkpoints, so it can be resumed.
            logger.exception("check-in generation failed", extra={"check_in_id": check_in_id})
            outcome = "timed_out" if isinstance(error, TimeoutError) else "failed"
            error_name = type(error).__name__
            # Our failure, not the user's: it doesn't use up one of their check-ins. (Only one
            # runs at a time, so the latest count is this run's.)
            if self.rate_limits:
                user_limiter.undo(_check_in_count(check_in.owner_id))
            await self.session.rollback()
            await self._mark_failed(check_in_id, steps, FAILED_REASON)
        except asyncio.CancelledError:
            outcome = "interrupted"
            raise
        finally:
            # Logged however the run ended, even if marking it failed went wrong too.
            summary = metrics.summary(outcome=outcome, duration_ms=elapsed_ms(started), error=error_name)
            logger.info("check-in run finished", extra={"check_in_id": check_in_id, "run_metrics": summary})
        await self._forget_run(check_in_id)

    async def _to_read(self, check_in: CheckInModel) -> CheckIn:
        proposals = await self.repository.list_proposals(check_in.id)
        return CheckIn(
            id=check_in.id,
            week_label=check_in.week_label,
            range_label=check_in.range_label,
            status=check_in.status,
            failure_reason=check_in.failure_reason,
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
            raise NotFound("Check-in not found")
        proposal = await self.repository.get_proposal(proposal_id, check_in_id)
        if proposal is None:
            raise NotFound("Proposal not found")
        if proposal.status != ProposalStatus.PENDING:
            raise Conflict(f"Proposal has already been decided ({proposal.status.value})")

        if payload.decision == "reject":
            proposal.status = ProposalStatus.REJECTED
        else:
            changes = proposal.changes
            status_after = ProposalStatus.APPLIED
            if payload.changes:
                overrides = {override.id: override.after for override in payload.changes}
                unknown = set(overrides) - {cast(str, change["id"]) for change in proposal.changes}
                if unknown:
                    # An edit can only adjust a value the proposal actually changes.
                    raise Invalid(
                        f"Not part of this proposal: {', '.join(sorted(unknown))}",
                    )
                changes = [
                    {**change, "after": overrides.get(cast(str, change["id"]), change["after"])}
                    for change in proposal.changes
                ]
                status_after = ProposalStatus.EDITED
            # Checked before anything is changed, so a refused proposal stays pending.
            if proposal.kind == ProposalKind.NUTRITION:
                await self.applier.nutrition(actor, check_in, proposal, changes)
            else:
                await self.applier.training(actor, check_in, changes)
            proposal.changes = changes
            proposal.status = status_after

        # Only now: a refused apply above leaves the proposal pending, with no decision time.
        proposal.decided_utc = datetime.now(UTC)
        try:
            await self.session.commit()
        except StaleDataError:
            # The routine was saved elsewhere (its exercises replaced) while this was applied.
            await self.session.rollback()
            raise Conflict(ROUTINE_CHANGED) from None
        await self.session.refresh(proposal)
        return _to_proposal_read(proposal)

    async def list_messages(self, check_in_id: str, actor: ActorContext) -> list[CoachMessage]:
        await self._owned_check_in(check_in_id, actor)
        return [
            CoachMessage(
                id=message.id,
                role=message.role,
                text=message.text,
                kind="answer" if message.role == MessageRole.USER else message.kind,
            )
            for message in await self.repository.list_messages(check_in_id)
        ]

    async def ask_coach(self, check_in_id: str, text: str, actor: ActorContext) -> CoachMessage:
        """Answer a question about the check-in. The question and the answer are stored
        together, only once there is an answer, so asking again after a failure repeats nothing.
        A question left unanswered gives its count back."""

        check_in = await self._owned_check_in(check_in_id, actor)
        if check_in.status in (CheckInStatus.RUNNING, CheckInStatus.FAILED):
            raise Conflict(CHAT_NOT_READY)
        # Counted from here on, where the paid model call is made.
        with counted_attempt(
            ("chat", actor.actor_id),
            CHAT_QUESTIONS_PER_USER,
            reason="That's a lot of questions for now.",
            counts=user_limiter,
            enabled=self.rate_limits,
        ):
            return await self._answer(check_in, text, actor)

    async def _answer(self, check_in: CheckInModel, text: str, actor: ActorContext) -> CoachMessage:
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

    async def _owned_check_in(self, check_in_id: str, actor: ActorContext) -> CheckInModel:
        check_in = await self.repository.get_owned(check_in_id, actor.actor_id)
        if check_in is None:
            raise NotFound("Check-in not found")
        return check_in
