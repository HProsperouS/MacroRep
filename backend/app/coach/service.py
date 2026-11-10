"""Check-in creation and retrieval, proposal decisions, and the chat's gating."""

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
from app.shared.exceptions import Conflict, Invalid, NotFound
from app.shared.rate_limit import CHAT_QUESTIONS_PER_USER, CHECK_INS_PER_USER
from app.shared.timezones import local_today
from app.shared.usage import counted_usage, give_back, give_back_latest, spend

from .agents.graph import run_agents
from .agents.metrics import RunMetrics, RunOutcome, elapsed_ms
from .agents.model import CoachModel
from .apply import ROUTINE_CHANGED, ProposalApplier
from .chat import CoachChat
from .models import CheckIn as CheckInModel
from .models import CheckInStatus, ProposalKind, ProposalStatus
from .models import Proposal as ProposalModel
from .pipeline import gather_step
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
INTERRUPTED_REASON = (
    "This check-in was interrupted before it finished. Nothing was changed; start a new one to try again."
)
RUNNING_PIPELINE: list[dict[str, str]] = [
    gather_step(),
    {"id": "propose", "title": "Draft proposals", "detail": "Reviewing your week…", "status": "running"},
]

logger = logging.getLogger(__name__)


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
        chat: CoachChat,
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
        self.chat = chat
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
        counted = (
            await spend(
                "check_in", actor.actor_id, CHECK_INS_PER_USER, reason="That's a lot of check-ins for today."
            )
            if self.rate_limits
            else None
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
            if counted is not None and not created:
                await give_back(counted)
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
                try:
                    await give_back_latest("check_in", check_in.owner_id)
                except Exception:
                    # Still mark the run failed below: a lost give-back only costs the user one count.
                    logger.warning("couldn't give back a check-in count", extra={"check_in_id": check_in_id})
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
        return await self.chat.list_messages(check_in_id)

    async def ask_coach(self, check_in_id: str, text: str, actor: ActorContext) -> CoachMessage:
        """Answer a question about the check-in. The question and the answer are stored
        together, only once there is an answer, so asking again after a failure repeats nothing.
        A question left unanswered gives its count back."""

        check_in = await self._owned_check_in(check_in_id, actor)
        if check_in.status in (CheckInStatus.RUNNING, CheckInStatus.FAILED):
            raise Conflict(CHAT_NOT_READY)
        # Counted from here on, where the paid model call is made.
        async with counted_usage(
            "chat",
            actor.actor_id,
            CHAT_QUESTIONS_PER_USER,
            reason="That's a lot of questions for now.",
            enabled=self.rate_limits,
        ):
            return await self.chat.ask(check_in, text, actor)

    async def _owned_check_in(self, check_in_id: str, actor: ActorContext) -> CheckInModel:
        check_in = await self.repository.get_owned(check_in_id, actor.actor_id)
        if check_in is None:
            raise NotFound("Check-in not found")
        return check_in
