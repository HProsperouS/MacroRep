"""Check-in creation and retrieval, proposal decisions, and coach chat."""

from __future__ import annotations

from datetime import date, timedelta
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
)
from app.analytics.training import average_rpe, completion_percent, planned_sessions
from app.analytics.weight import trend_on_or_before
from app.body.service import trend_by_date
from app.identity.dependencies import ActorContext
from app.profile.models import Profile
from app.profile.repository import ProfileRepository
from app.progress.repository import ProgressRepository
from app.shared.timezones import local_today, user_zone
from app.shared.validation import ensure_plausible_calories

from . import pipeline
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
    )


CHECK_IN_WINDOW_DAYS = 7
MIN_FOOD_LOG_DAYS = 4
MIN_WEIGH_INS = 2
# Mirrors ProgressService's fallback for a user whose profile was never provisioned.
_FALLBACK_TARGET_CALORIES = 2000
# Same bounds as the Profile page's targets form, so a coach proposal can't set a
# target the user couldn't type in themselves. See docs/follow-ups.md.
MIN_TARGET_CALORIES = 1_000
MAX_TARGET_CALORIES = 6_000


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
        return await self._to_read(check_in)

    async def start_check_in(self, idempotency_key: str, actor: ActorContext) -> tuple[CheckIn, bool]:
        """Create a check-in for the last 7 days; returns it and whether it was newly created.

        Idempotent per (user, key): replaying a key returns the check-in it
        originally created instead of generating another one. Only a
        successful creation consumes a key, so a request refused for missing
        data can be retried with the same key once the data is logged.
        """

        existing = await self.repository.get_by_idempotency_key(actor.actor_id, idempotency_key)
        if existing is not None:
            return await self._to_read(existing), False

        current = await self.repository.get_current(actor.actor_id)
        if current is not None and any(
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
        snapshot = await self._snapshot_week(actor.actor_id, profile, start, today, zone)

        week_label = f"Week {await self.repository.count_for_owner(actor.actor_id) + 1}"
        draft = pipeline.draft_check_in(
            week_label=week_label,
            avg_calories=cast(float, snapshot["avg_calories"]),
            target_calories=cast(int, snapshot["target_calories"]),
            adherence_percent=cast(float, snapshot["adherence_percent"]),
            partial_days=cast(int, snapshot["partial_days"]),
            target_gap_kcal=cast(int, snapshot["target_gap_kcal"]),
            workouts_done=cast(int, snapshot["workouts_done"]),
            workouts_planned=cast(int, snapshot["workouts_planned"]),
            completion_percent=cast("float | None", snapshot["completion_percent"]),
            avg_rpe=cast("float | None", snapshot["avg_rpe"]),
            weight_change_kg=cast(float, snapshot["weight_change_kg"]),
            goal_rate_kg_per_week=cast(float, snapshot["goal_rate_kg_per_week"]),
        )

        check_in = CheckInModel(
            owner_id=actor.actor_id,
            week_label=week_label,
            range_label=f"{start.isoformat()} – {today.isoformat()}",
            status=CheckInStatus.NEEDS_REVIEW if draft.proposals else CheckInStatus.REVIEWED,
            summary=draft.summary,
            stats=draft.stats,
            pipeline=draft.pipeline,
            suggested_questions=draft.suggested_questions,
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

        await self.repository.add_proposals(
            [
                ProposalModel(
                    check_in_id=check_in.id,
                    kind=ProposalKind(proposal.kind),
                    headline=proposal.headline,
                    changes=[change.__dict__ for change in proposal.changes],
                    evidence=proposal.evidence,
                    reviewer_note=proposal.reviewer_note,
                )
                for proposal in draft.proposals
            ]
        )
        await self.session.commit()
        return await self._to_read(check_in), True

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

        target_calories = profile.target_calories if profile else _FALLBACK_TARGET_CALORIES
        # Non-None: the data gate above guarantees at least MIN_FOOD_LOG_DAYS logged days.
        avg_calories = cast(float, average_daily_calories(calories_by_date))
        # `end` is today: still being logged, so it's left out of completeness and the target gap.
        statuses = day_statuses(calories_by_date, start, end, target_calories, end)
        completeness = logging_completeness(statuses.values())
        finished_logged = [
            calories_by_date[day]
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
        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "avg_calories": round(avg_calories, 1),
            "target_calories": target_calories,
            "food_log_days": len(calories_by_date),
            "adherence_percent": logging_adherence_percent(len(calories_by_date), CHECK_IN_WINDOW_DAYS),
            "complete_days": completeness.complete,
            "partial_days": completeness.partial,
            "missing_days": completeness.missing,
            "target_gap_kcal": target_gap_kcal(finished_logged, target_calories),
            "weigh_ins": len(weigh_ins_in_window),
            "weight_change_kg": round(trend_end - trend_start, 2),
            "goal_rate_kg_per_week": float(profile.weekly_rate_kg) if profile else 0.0,
            "workouts_done": workouts_done,
            "workouts_planned": workouts_planned,
            "completion_percent": completion_percent(workouts_done, workouts_planned),
            "avg_rpe": average_rpe(rpe for _, rpe in rpe_entries),
        }

    async def _to_read(self, check_in: CheckInModel) -> CheckIn:
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
                await self._apply_nutrition_targets(actor, changes)
            # Training proposals are only recorded for now; they don't edit the weekly plan yet.
            proposal.changes = changes
            proposal.status = status_after

        await self.session.commit()
        await self.session.refresh(proposal)
        return _to_proposal_read(proposal)

    async def _apply_nutrition_targets(self, actor: ActorContext, changes: list[dict[str, object]]) -> None:
        """Write an accepted calorie change to the user's daily target.

        Raises 422 when the new target is outside the range the app allows, or
        far below what the macros add up to, leaving the targets untouched.
        """

        calories = next((change["after"] for change in changes if change["id"] == "calories"), None)
        if calories is None:
            return
        target = round(cast(float, calories))
        profile = await self.profiles.get(actor.actor_id)
        if profile is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Set up your profile before applying targets")
        if not MIN_TARGET_CALORIES <= target <= MAX_TARGET_CALORIES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"A daily target of {target:,} kcal is outside the allowed "
                f"{MIN_TARGET_CALORIES:,}-{MAX_TARGET_CALORIES:,} kcal. Edit it to a value in range.",
            )
        try:
            ensure_plausible_calories(
                target,
                float(profile.target_protein_g),
                float(profile.target_carbs_g),
                float(profile.target_fat_g),
            )
        except ValueError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
        profile.target_calories = target
        profile.touch()

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
