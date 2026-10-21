"""Owner-scoped coach check-in, proposal, and message persistence."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import case, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db import get_owned as _get_owned
from app.shared.persistence.mixins import utc_now

from .models import CheckIn, CheckInStatus, CoachMessage, MessageRole, Proposal, ProposalKind, ProposalStatus


class CoachRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_current(self, owner_id: str) -> CheckIn | None:
        return cast(
            "CheckIn | None",
            await self.session.scalar(
                select(CheckIn)
                .where(CheckIn.owner_id == owner_id)
                .order_by(CheckIn.created_utc.desc())
                .limit(1)
            ),
        )

    async def get(self, check_in_id: str) -> CheckIn | None:
        """Any user's check-in, for the background run that generates it (no request owner)."""

        return await self.session.get(CheckIn, check_in_id)

    async def get_owned(self, check_in_id: str, owner_id: str) -> CheckIn | None:
        return await _get_owned(self.session, CheckIn, check_in_id, owner_id)

    async def get_by_idempotency_key(self, owner_id: str, idempotency_key: str) -> CheckIn | None:
        return cast(
            "CheckIn | None",
            await self.session.scalar(
                select(CheckIn).where(
                    CheckIn.owner_id == owner_id, CheckIn.idempotency_key == idempotency_key
                )
            ),
        )

    async def count_for_owner(self, owner_id: str) -> int:
        """Check-ins that didn't fail: a failed one is retried under the same week number."""

        return int(
            await self.session.scalar(
                select(func.count()).where(
                    CheckIn.owner_id == owner_id, CheckIn.status != CheckInStatus.FAILED
                )
            )
            or 0
        )

    async def finish_run(self, check_in_id: str, **values: object) -> bool:
        """Move a RUNNING check-in on to ``values`` (status and its results), in one
        conditional update. False when it is no longer RUNNING, because the run already
        finished or was marked failed, so two writers can never both win."""

        result = cast(
            "CursorResult[Any]",
            await self.session.execute(
                update(CheckIn)
                .where(CheckIn.id == check_in_id, CheckIn.status == CheckInStatus.RUNNING)
                .values(**values, updated_utc=utc_now())
            ),
        )
        return bool(result.rowcount == 1)

    async def add_check_in(self, check_in: CheckIn) -> CheckIn:
        self.session.add(check_in)
        await self.session.flush()
        return check_in

    async def pending_proposal(self, check_in_id: str, kind: ProposalKind) -> Proposal | None:
        """The check-in's pending proposal of ``kind``, read afresh from the database (not the
        session's copy) with its check-in locked, so a decision or another revision made
        meanwhile is seen, and two revisions can't both add one."""

        await self.session.execute(select(CheckIn.id).where(CheckIn.id == check_in_id).with_for_update())
        return cast(
            "Proposal | None",
            await self.session.scalar(
                select(Proposal)
                .where(
                    Proposal.check_in_id == check_in_id,
                    Proposal.kind == kind,
                    Proposal.status == ProposalStatus.PENDING,
                )
                .execution_options(populate_existing=True)
            ),
        )

    async def list_proposals(self, check_in_id: str) -> list[Proposal]:
        return list(await self.session.scalars(select(Proposal).where(Proposal.check_in_id == check_in_id)))

    async def list_proposals_for_check_ins(self, check_in_ids: list[str]) -> dict[str, list[Proposal]]:
        """Proposals for several check-ins in one query, grouped by check-in id."""

        if not check_in_ids:
            return {}
        rows = await self.session.scalars(select(Proposal).where(Proposal.check_in_id.in_(check_in_ids)))
        grouped: dict[str, list[Proposal]] = {check_in_id: [] for check_in_id in check_in_ids}
        for proposal in rows:
            grouped[proposal.check_in_id].append(proposal)
        return grouped

    async def get_proposal(self, proposal_id: str, check_in_id: str) -> Proposal | None:
        proposal = await self.session.get(Proposal, proposal_id)
        if proposal is None or proposal.check_in_id != check_in_id:
            return None
        return proposal

    async def add_proposals(self, proposals: list[Proposal]) -> None:
        self.session.add_all(proposals)
        await self.session.flush()

    async def list_messages(self, check_in_id: str, latest: int | None = None) -> list[CoachMessage]:
        """The conversation oldest first, or only its ``latest`` messages."""

        newest_first = await self.session.scalars(
            select(CoachMessage)
            .where(CoachMessage.check_in_id == check_in_id)
            # A question and its answer are saved together; should their times tie, the answer
            # sorts first here, so after the question once reversed. Spelled out, because
            # Explicit, rather than leaning on the enum's declaration order.
            .order_by(
                CoachMessage.created_utc.desc(), case((CoachMessage.role == MessageRole.COACH, 0), else_=1)
            )
            .limit(latest)
        )
        return list(reversed(list(newest_first)))

    async def add_message(self, message: CoachMessage) -> CoachMessage:
        self.session.add(message)
        await self.session.flush()
        return message
