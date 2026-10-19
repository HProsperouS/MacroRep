"""Check-in creation and retrieval, proposal decisions, and coach chat."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.nutrition import (
    DayStatus,
    average_daily_calories,
    day_statuses,
    logging_adherence_percent,
    logging_completeness,
    target_gap_kcal,
    targets_by_date,
)
from app.analytics.training import average_rpe, completion_percent, planned_sessions
from app.analytics.weight import trend_on_or_before
from app.body.service import trend_by_date
from app.identity.dependencies import ActorContext
from app.profile.models import Profile, TargetSource
from app.profile.repository import ProfileRepository
from app.profile.service import DEFAULT_TARGETS
from app.progress.repository import ProgressRepository
from app.shared.timezones import local_today, user_zone
from app.shared.validation import ensure_plausible_calories

from .agents.checkpoint import get_checkpointer
from .agents.graph import run_agents
from .agents.model import get_coach_model
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
        decided_at=_as_utc(proposal.decided_utc) if proposal.decided_utc else None,
    )


def _as_utc(moment: datetime) -> datetime:
    # SQLite hands back naive datetimes; everything is stored in UTC.
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


CHECK_IN_WINDOW_DAYS = 7
MIN_FOOD_LOG_DAYS = 4
MIN_WEIGH_INS = 2
# Same bounds as the Profile page's targets form, so a coach proposal can't set a
# target the user couldn't type in themselves. See docs/follow-ups.md.
MIN_TARGET_CALORIES = 1_000
MAX_TARGET_CALORIES = 6_000
# A run that hasn't finished by then is abandoned and marked failed.
RUN_TIMEOUT_SECONDS = 120
# A check-in still RUNNING this long after it started was lost (e.g. a restart mid-run).
STALE_RUN_AFTER = timedelta(minutes=10)
FAILED_REASON = (
    "Something went wrong while preparing this check-in. Nothing was changed; start a new one to try again."
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


async def _forget_run(check_in_id: str) -> None:
    """Drop a finished run's checkpoints: the check-in row holds the outcome, and nothing
    resumes a run that ended, so keeping them would only grow the store."""

    try:
        await get_checkpointer().adelete_thread(check_in_id)
    except Exception:
        logger.warning("couldn't delete check-in checkpoints", extra={"check_in_id": check_in_id})


def _failed_pipeline(steps: list[dict[str, str]]) -> list[dict[str, str]]:
    """The steps as they stood, with the one that was running marked failed."""

    return [{**step, "status": "failed"} if step["status"] == "running" else step for step in steps]


class CoachService:
    def __init__(
        self,
        session: AsyncSession,
        repository: CoachRepository,
        week_data: ProgressRepository,
        profiles: ProfileRepository,
    ) -> None:
        self.session = session
        self.repository = repository
        self.week_data = week_data
        self.profiles = profiles

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
        if datetime.now(UTC) - _as_utc(check_in.created_utc) < STALE_RUN_AFTER:
            return
        await self._mark_failed(check_in.id, check_in.pipeline, INTERRUPTED_REASON)
        await self.session.refresh(check_in)

    async def _mark_failed(self, check_in_id: str, steps: list[dict[str, str]], reason: str) -> None:
        """Mark a RUNNING check-in failed. Does nothing if it already moved on, e.g. finished meanwhile."""

        if await self.repository.finish_run(
            check_in_id, status=CheckInStatus.FAILED, failure_reason=reason, pipeline=_failed_pipeline(steps)
        ):
            await self.session.commit()

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
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "Your check-in is still being prepared. It'll be ready shortly."
                )
            if any(
                proposal.status == ProposalStatus.PENDING
                for proposal in await self.repository.list_proposals(current.id)
            ):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Your current check-in still has proposals to review. Apply or reject them first.",
                )

        profile = await self.profiles.get(actor.actor_id)
        zone = user_zone(profile.timezone if profile else None)
        today = local_today(zone)
        start = today - timedelta(days=CHECK_IN_WINDOW_DAYS - 1)
        # Checked and frozen now, so a lack of data is refused at once and the proposals,
        # generated afterwards in the background, rest on exactly these numbers.
        snapshot = await self._snapshot_week(actor.actor_id, profile, start, today, zone)

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
        try:
            draft = await asyncio.wait_for(
                run_agents(
                    snapshot, get_coach_model(), thread_id=check_in_id, checkpointer=get_checkpointer()
                ),
                timeout=RUN_TIMEOUT_SECONDS,
            )
            if await self.repository.finish_run(
                check_in_id,
                status=CheckInStatus.NEEDS_REVIEW if draft.proposals else CheckInStatus.REVIEWED,
                summary=draft.summary,
                stats=draft.stats,
                pipeline=draft.pipeline,
                suggested_questions=draft.suggested_questions,
            ):
                await self.repository.add_proposals(
                    [ProposalModel.from_draft(check_in_id, proposal) for proposal in draft.proposals]
                )
                await self.session.commit()
            # Otherwise it was already marked failed (or finished) while this run was drafting.
        except Exception:
            # Not asyncio.CancelledError (a BaseException): a run stopped at shutdown stays
            # RUNNING, with its checkpoints, so it can be resumed.
            logger.exception("check-in generation failed", extra={"check_in_id": check_in_id})
            await self.session.rollback()
            await self._mark_failed(check_in_id, steps, FAILED_REASON)
        await _forget_run(check_in_id)

    async def _snapshot_week(
        self, owner_id: str, profile: Profile | None, start: date, end: date, zone: ZoneInfo
    ) -> dict[str, object]:
        """Gather the week's metrics, refusing with 422 when there's too little data to judge.

        ``end`` is the user's today, in ``zone``.
        """

        calories_by_date = await self.week_data.daily_calories(owner_id, start, end)
        history = await self.week_data.weigh_ins_up_to(owner_id, end)
        weigh_ins_in_window = [row for row in history if row.log_date >= start]

        missing: list[str] = []
        if len(calories_by_date) < MIN_FOOD_LOG_DAYS:
            missing.append(
                f"log food on at least {MIN_FOOD_LOG_DAYS} of the last {CHECK_IN_WINDOW_DAYS} days "
                f"({len(calories_by_date)} so far)"
            )
        if len(weigh_ins_in_window) < MIN_WEIGH_INS:
            missing.append(f"weigh in at least {MIN_WEIGH_INS} times ({len(weigh_ins_in_window)} so far)")
        if missing:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Not enough data for a check-in yet: {' and '.join(missing)}.",
            )

        trends = trend_by_date(history)
        # A weigh-in from before the window anchors the start; otherwise the
        # window's own first reading does.
        trend_start = trend_on_or_before(trends, start)
        if trend_start is None:
            trend_start = trends[weigh_ins_in_window[0].log_date]
        trend_end = trends[weigh_ins_in_window[-1].log_date]

        # Each day is judged against the target in effect that day; proposals start from today's.
        target_versions = await self.profiles.target_history(owner_id)
        current_targets = target_versions[-1] if target_versions else None
        target_by_date = targets_by_date(
            [(row.effective_date, float(row.calories)) for row in target_versions],
            start,
            end,
            DEFAULT_TARGETS.calories,
        )
        target_calories = round(target_by_date[end])
        # Non-None: the data gate above guarantees at least MIN_FOOD_LOG_DAYS logged days.
        avg_calories = cast(float, average_daily_calories(calories_by_date))
        # `end` is today: still being logged, so it's left out of completeness and the target gap.
        statuses = day_statuses(calories_by_date, start, end, target_by_date, end)
        completeness = logging_completeness(statuses.values())
        finished_logged = [
            (calories_by_date[day], target_by_date[day])
            for day, day_status in statuses.items()
            if day_status in (DayStatus.COMPLETE, DayStatus.PARTIAL)
        ]
        workouts_done = await self.week_data.workouts_done(owner_id, start, end, zone)
        workouts_planned = planned_sessions(
            await self.week_data.plan_weekdays(owner_id),
            start,
            end,
            end,
            trained_today=await self.week_data.workouts_done(owner_id, end, end, zone) > 0,
        )
        rpe_entries = await self.week_data.rpe_entries(owner_id, start, end, zone)
        routines = await self.week_data.scheduled_routines(owner_id)
        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "avg_calories": round(avg_calories, 1),
            "target_calories": target_calories,
            # The targets version the proposals were made against; applying one checks it is still current.
            "target_version": current_targets.version if current_targets else None,
            "food_log_days": len(calories_by_date),
            "adherence_percent": logging_adherence_percent(len(calories_by_date), CHECK_IN_WINDOW_DAYS),
            "complete_days": completeness.complete,
            "partial_days": completeness.partial,
            "missing_days": completeness.missing,
            "target_gap_kcal": target_gap_kcal(finished_logged),
            "weigh_ins": len(weigh_ins_in_window),
            "weight_change_kg": round(trend_end - trend_start, 2),
            "goal_rate_kg_per_week": float(profile.weekly_rate_kg) if profile else 0.0,
            "workouts_done": workouts_done,
            "workouts_planned": workouts_planned,
            "completion_percent": completion_percent(workouts_done, workouts_planned),
            "avg_rpe": average_rpe(rpe for _, rpe in rpe_entries),
            # What the workout agent may adjust, and how each exercise has been going.
            "routines": routines,
            "exercise_trends": await self.week_data.exercise_trends(
                owner_id,
                sorted(
                    {
                        cast(str, e["exercise_id"])
                        for r in routines
                        for e in cast(list[dict[str, object]], r["exercises"])
                    }
                ),
                start,
                end,
                zone,
            ),
            "equipment": list(profile.equipment) if profile else [],
            "goal": profile.goal.value if profile else "maintain",
        }

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
        else:
            changes = proposal.changes
            status_after = ProposalStatus.APPLIED
            if payload.changes:
                overrides = {override.id: override.after for override in payload.changes}
                unknown = set(overrides) - {cast(str, change["id"]) for change in proposal.changes}
                if unknown:
                    # An edit can only adjust a value the proposal actually changes.
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        f"Not part of this proposal: {', '.join(sorted(unknown))}",
                    )
                changes = [
                    {**change, "after": overrides.get(cast(str, change["id"]), change["after"])}
                    for change in proposal.changes
                ]
                status_after = ProposalStatus.EDITED
            # Checked before anything is changed, so a refused proposal stays pending.
            if proposal.kind == ProposalKind.NUTRITION:
                await self._apply_nutrition_targets(actor, check_in, proposal, changes)
            # Training proposals are only recorded for now; they don't edit the weekly plan yet.
            proposal.changes = changes
            proposal.status = status_after

        # Only now: a refused apply above leaves the proposal pending, with no decision time.
        proposal.decided_utc = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(proposal)
        return _to_proposal_read(proposal)

    async def _apply_nutrition_targets(
        self,
        actor: ActorContext,
        check_in: CheckInModel,
        proposal: ProposalModel,
        changes: list[dict[str, object]],
    ) -> None:
        """Record an accepted calorie change as a new version of the user's targets, from today.

        Raises 409 when the targets changed after the check-in was made, since the proposal
        was worked out from the old ones, and 422 when the new target is outside the range
        the app allows or far below what the macros add up to. Either way nothing is changed.
        """

        calories = next((change["after"] for change in changes if change["id"] == "calories"), None)
        if calories is None:
            return
        target = round(cast(float, calories))
        profile = await self.profiles.get(actor.actor_id)
        current = await self.profiles.current_targets(actor.actor_id)
        if profile is None or current is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Set up your profile before applying targets")
        expected_version = (check_in.input_snapshot or {}).get("target_version")
        # Check-ins made before targets were versioned have no version to compare.
        if expected_version is not None and expected_version != current.version:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Your targets changed after this check-in was made, so its proposal is out of date. "
                "Reject it and start a new check-in.",
            )
        if not MIN_TARGET_CALORIES <= target <= MAX_TARGET_CALORIES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"A daily target of {target:,} kcal is outside the allowed "
                f"{MIN_TARGET_CALORIES:,}-{MAX_TARGET_CALORIES:,} kcal. Edit it to a value in range.",
            )
        protein, carbs, fat = float(current.protein_g), float(current.carbs_g), float(current.fat_g)
        try:
            ensure_plausible_calories(target, protein, carbs, fat)
        except ValueError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
        try:
            # Numbered after the targets checked above: a change saved since then is refused, not overwritten.
            await self.profiles.add_target_version(
                actor.actor_id,
                previous=current,
                calories=target,
                protein=protein,
                carbs=carbs,
                fat=fat,
                effective_date=local_today(user_zone(profile.timezone)),
                source=TargetSource.CHECK_IN,
                proposal_id=proposal.id,
            )
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Your targets were just changed elsewhere, please retry"
            ) from None

    async def ask_coach(self, check_in_id: str, text: str, actor: ActorContext) -> CoachMessage:
        check_in = await self.repository.get_owned(check_in_id, actor.actor_id)
        if check_in is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Check-in not found")

        await self.repository.add_message(
            CoachMessageModel(
                check_in_id=check_in_id, owner_id=actor.actor_id, role=MessageRole.USER, text=text
            )
        )
        # Placeholder reply: Coach Chat is a stretch feature (plan.md §8.9), not built yet.
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
