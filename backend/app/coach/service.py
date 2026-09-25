"""Check-in creation and retrieval, proposal decisions, and coach chat."""

from __future__ import annotations

from datetime import date, timedelta
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.body.service import compute_trend_series
from app.identity.dependencies import ActorContext
from app.profile.repository import ProfileRepository
from app.progress.repository import ProgressRepository

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


def _trend_on_or_before(trend_by_date: dict[str, float], day: date) -> float | None:
    """The latest trend weight recorded on or before `day` (keys are in date order)."""

    latest: float | None = None
    for iso_date, trend in trend_by_date.items():
        if iso_date > day.isoformat():
            break
        latest = trend
    return latest


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

        today = date.today()
        start = today - timedelta(days=CHECK_IN_WINDOW_DAYS - 1)
        snapshot = await self._snapshot_week(actor.actor_id, start, today)

        week_label = f"Week {await self.repository.count_for_owner(actor.actor_id) + 1}"
        draft = pipeline.draft_check_in(
            week_label=week_label,
            avg_calories=cast(float, snapshot["avg_calories"]),
            target_calories=cast(int, snapshot["target_calories"]),
            adherence_percent=cast(float, snapshot["adherence_percent"]),
            workouts_done=cast(int, snapshot["workouts_done"]),
            workouts_planned=cast(int, snapshot["workouts_planned"]),
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

    async def _snapshot_week(self, owner_id: str, start: date, end: date) -> dict[str, object]:
        """Gather the week's metrics, refusing with 422 when there's too little data to judge."""

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

        trend_by_date = compute_trend_series(history)
        # A weigh-in from before the window anchors the start; otherwise the
        # window's own first reading does.
        trend_start = _trend_on_or_before(trend_by_date, start)
        if trend_start is None:
            trend_start = trend_by_date[weigh_ins_in_window[0].log_date.isoformat()]
        trend_end = trend_by_date[weigh_ins_in_window[-1].log_date.isoformat()]

        profile = await self.profiles.get(owner_id)
        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "avg_calories": round(sum(calories_by_date.values()) / len(calories_by_date), 1),
            "target_calories": profile.target_calories if profile else _FALLBACK_TARGET_CALORIES,
            "food_log_days": len(calories_by_date),
            "adherence_percent": round(len(calories_by_date) / CHECK_IN_WINDOW_DAYS * 100, 1),
            "weigh_ins": len(weigh_ins_in_window),
            "weight_change_kg": round(trend_end - trend_start, 2),
            "goal_rate_kg_per_week": float(profile.weekly_rate_kg) if profile else 0.0,
            "workouts_done": await self.week_data.workouts_done(owner_id, start, end),
            "workouts_planned": await self.week_data.workouts_planned_per_week(owner_id),
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
