"""Owner-scoped coach check-in, proposal, and message persistence."""

from __future__ import annotations

from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db import get_owned as _get_owned

from .models import CheckIn, CoachMessage, Proposal


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
        return int(await self.session.scalar(select(func.count()).where(CheckIn.owner_id == owner_id)) or 0)

    async def add_check_in(self, check_in: CheckIn) -> CheckIn:
        self.session.add(check_in)
        await self.session.flush()
        return check_in

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

    async def list_messages(self, check_in_id: str) -> list[CoachMessage]:
        return list(
            await self.session.scalars(
                select(CoachMessage)
                .where(CoachMessage.check_in_id == check_in_id)
                .order_by(CoachMessage.created_utc.asc())
            )
        )

    async def add_message(self, message: CoachMessage) -> CoachMessage:
        self.session.add(message)
        await self.session.flush()
        return message
