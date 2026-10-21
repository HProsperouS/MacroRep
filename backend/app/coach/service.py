"""Check-in creation and retrieval, proposal decisions, and coach chat."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

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
from app.core.config import get_settings
from app.identity.dependencies import ActorContext
from app.profile.models import Profile, TargetSource
from app.profile.repository import ProfileRepository
from app.profile.service import DEFAULT_TARGETS
from app.progress.repository import ProgressRepository
from app.shared.rate_limit import CHAT_QUESTIONS_PER_USER, CHECK_INS_PER_USER, count_attempt, user_limiter
from app.shared.timezones import local_today, user_zone

# The same bounds as the targets the user sets, so a proposal can't set one they couldn't type in.
from app.shared.validation import MAX_TARGET_CALORIES, MIN_TARGET_CALORIES, ensure_plausible_calories
from app.workout.models import WorkoutPlanEntry, WorkoutPlanExercise
from app.workout.repository import WorkoutPlanRepository
from app.workout.targets import (
    TARGET_FIELDS,
    TargetField,
    adjust_targets,
    routine_revision,
    working_targets,
)

from .agents import limits
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
from .agents.checkpoint import get_checkpointer
from .agents.graph import run_agents
from .agents.metrics import RunMetrics, RunOutcome, elapsed_ms
from .agents.model import CoachModel, get_coach_model
from .agents.validate import training_change_error
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
ROUTINE_GONE = (
    "The routine this change was for no longer has that exercise. Reject it and start a new check-in."
)
ROUTINE_CHANGED = (
    "Your routine changed after this check-in was made, so its proposal is out of date. "
    "Reject it and start a new check-in."
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


async def _forget_run(check_in_id: str) -> None:
    """Drop a finished run's checkpoints: the check-in row holds the outcome, and nothing
    resumes a run that ended, so keeping them would only grow the store."""

    try:
        await get_checkpointer().adelete_thread(check_in_id)
    except Exception:
        logger.warning("couldn't delete check-in checkpoints", extra={"check_in_id": check_in_id})


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
        """Mark a RUNNING check-in failed, and drop its checkpoints: a failed run is never
        resumed. Does nothing if it already moved on, e.g. finished meanwhile."""

        if await self.repository.finish_run(
            check_in_id, status=CheckInStatus.FAILED, failure_reason=reason, pipeline=_failed_pipeline(steps)
        ):
            await self.session.commit()
            await _forget_run(check_in_id)

    async def start_check_in(
        self, idempotency_key: str, actor: ActorContext, *, limit_check_ins: bool = True
    ) -> tuple[CheckIn, bool]:
        """Create a check-in for the last 7 days; returns it and whether it was newly created.

        Idempotent per (user, key): replaying a key returns the check-in it
        originally created instead of generating another one. Only a
        successful creation consumes a key, so a request refused for missing
        data can be retried with the same key once the data is logged.
        With ``limit_check_ins``, each user gets ``CHECK_INS_PER_USER`` (then 429);
        a run that fails gives its one back.
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
        # Counted before the row is written, so starts sent at once can't all slip under the
        # limit, and given back unless the row is written: then no run, and no model calls.
        count_key = _check_in_count(actor.actor_id)
        if limit_check_ins:
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
            if limit_check_ins and not created:
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
            model = get_coach_model()
            metrics.model = model.name
            draft = await asyncio.wait_for(
                run_agents(
                    snapshot,
                    model,
                    thread_id=check_in_id,
                    checkpointer=get_checkpointer(),
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
            if get_settings().rate_limits_enabled:
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
            else:
                await self._apply_training_changes(actor, check_in, changes)
            proposal.changes = changes
            proposal.status = status_after

        # Only now: a refused apply above leaves the proposal pending, with no decision time.
        proposal.decided_utc = datetime.now(UTC)
        try:
            await self.session.commit()
        except StaleDataError:
            # The routine was saved elsewhere (its exercises replaced) while this was applied.
            await self.session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, ROUTINE_CHANGED) from None
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

    async def _apply_training_changes(
        self, actor: ActorContext, check_in: CheckInModel, changes: list[dict[str, object]]
    ) -> None:
        """Write accepted training changes to the user's routines, all of them or none.

        Raises 409 when a routine or exercise is gone, or the routine was saved again after
        the check-in (so the proposal is out of date), and 422 when an edited value is past
        the limits. Nothing is changed then. Every change is checked against the routine as
        the check-in saw it, then applied weight and reps first, the number of sets last.
        """

        plans = WorkoutPlanRepository(self.session)
        seen = {
            cast(str, routine["routine_id"]): routine
            for routine in cast(list[dict[str, Any]], (check_in.input_snapshot or {}).get("routines") or [])
        }
        routines: dict[str, WorkoutPlanEntry] = {}
        exercises: dict[str, list[WorkoutPlanExercise]] = {}
        planned_changes: dict[str, tuple[WorkoutPlanExercise, list[tuple[TargetField, float]]]] = {}
        for change in changes:
            routine_id, exercise_id, field = (
                change.get("routine_id"),
                change.get("exercise_id"),
                change.get("field"),
            )
            if (
                not isinstance(routine_id, str)
                or not isinstance(exercise_id, str)
                or field not in TARGET_FIELDS
            ):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, "This change can't be applied to a routine."
                )
            if routine_id not in routines:
                routine = await plans.get(routine_id)
                if routine is None or routine.owner_id != actor.actor_id:
                    raise HTTPException(status.HTTP_409_CONFLICT, ROUTINE_GONE)
                # Snapshots from before revisions were recorded fall back to the value check below.
                revision = seen.get(routine_id, {}).get("revision")
                if revision is not None and revision != routine_revision(routine):
                    raise HTTPException(status.HTTP_409_CONFLICT, ROUTINE_CHANGED)
                routines[routine_id] = routine
                exercises[routine_id] = await plans.list_exercises(routine_id)
            # The first occurrence, as the snapshot described it to the agent.
            planned = next((pe for pe in exercises[routine_id] if pe.exercise_id == exercise_id), None)
            if planned is None:
                raise HTTPException(status.HTTP_409_CONFLICT, ROUTINE_GONE)
            target: TargetField = field
            before, after = float(cast(float, change["before"])), float(cast(float, change["after"]))
            current = working_targets(planned.planned_sets)[target]
            if current is None or abs(current - before) > 1e-9:
                raise HTTPException(status.HTTP_409_CONFLICT, ROUTINE_CHANGED)
            error = training_change_error(target, before, after)
            if error is not None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{change['label']}: {error}")
            planned_changes.setdefault(planned.id, (planned, []))[1].append((target, after))

        for planned, targets in planned_changes.values():
            sets = list(planned.planned_sets)
            # Sets last, so a weight change scales the sets the check-in saw, then any are added or dropped.
            for target, after in sorted(targets, key=lambda item: item[0] == "working_sets"):
                sets = adjust_targets(sets, target, after, load_step=limits.LOAD_STEP_KG)
            planned.planned_sets = sets
        for routine in routines.values():
            routine.touch()

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

    async def ask_coach(
        self, check_in_id: str, text: str, actor: ActorContext, *, limit_questions: bool = True
    ) -> CoachMessage:
        """Answer a question about the check-in. The question and the answer are stored
        together, only once there is an answer, so asking again after a failure repeats nothing.
        With ``limit_questions``, each user gets ``CHAT_QUESTIONS_PER_USER`` (then 429); a
        question left unanswered gives its one back."""

        check_in = await self._owned_check_in(check_in_id, actor)
        if check_in.status in (CheckInStatus.RUNNING, CheckInStatus.FAILED):
            raise HTTPException(status.HTTP_409_CONFLICT, CHAT_NOT_READY)
        # Counted from here on, where the paid model call is made.
        count_key = ("chat", actor.actor_id)
        if limit_questions:
            count_attempt(
                (count_key, CHAT_QUESTIONS_PER_USER),
                reason="That's a lot of questions for now.",
                counts=user_limiter,
            )
        try:
            return await self._answer(check_in, text, actor)
        except Exception:
            # Our failure, not the user's: it doesn't use up one of their questions.
            if limit_questions:
                user_limiter.undo(count_key)
            raise

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
        model = get_coach_model()
        answer = await answer_question(model, context, check_in_id)
        if answer is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, CHAT_UNAVAILABLE)

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
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, CHAT_UNAVAILABLE)
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
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Check-in not found")
        return check_in
