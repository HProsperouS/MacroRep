"""Coach check-in routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext, get_current_actor
from app.profile.repository import ProfileRepository
from app.progress.repository import ProgressRepository
from app.shared.persistence import get_session

from .repository import CoachRepository
from .schemas import AskCoachInput, CheckIn, CoachMessage, Proposal, ProposalDecisionInput
from .service import CoachService

router = APIRouter(prefix="/api/coach", tags=["coach"])


def get_coach_service(session: Annotated[AsyncSession, Depends(get_session)]) -> CoachService:
    return CoachService(
        session, CoachRepository(session), ProgressRepository(session), ProfileRepository(session)
    )


CoachServiceDep = Annotated[CoachService, Depends(get_coach_service)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("/check-ins/current", response_model=CheckIn | None)
async def get_current_check_in(actor: ActorDep, service: CoachServiceDep) -> CheckIn | None:
    return await service.get_current(actor)


@router.post(
    "/check-ins",
    response_model=CheckIn,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Replay of an Idempotency-Key already used: the check-in it created."},
        409: {"description": "The current check-in still has proposals awaiting a decision."},
        422: {"description": "Not enough food or weigh-in data in the last 7 days."},
    },
)
async def start_check_in(
    response: Response,
    actor: ActorDep,
    service: CoachServiceDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
) -> CheckIn:
    """Review the last 7 days and draft proposals. Safe to retry with the same Idempotency-Key."""

    check_in, created = await service.start_check_in(idempotency_key, actor)
    if not created:
        response.status_code = status.HTTP_200_OK
    return check_in


@router.post("/check-ins/{check_in_id}/proposals/{proposal_id}/decision", response_model=Proposal)
async def decide_proposal(
    check_in_id: str,
    proposal_id: str,
    payload: ProposalDecisionInput,
    actor: ActorDep,
    service: CoachServiceDep,
) -> Proposal:
    return await service.decide_proposal(check_in_id, proposal_id, payload, actor)


@router.post("/check-ins/{check_in_id}/messages", response_model=CoachMessage)
async def ask_coach(
    check_in_id: str, payload: AskCoachInput, actor: ActorDep, service: CoachServiceDep
) -> CoachMessage:
    return await service.ask_coach(check_in_id, payload.text, actor)
