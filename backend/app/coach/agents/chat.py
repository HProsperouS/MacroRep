"""Coach Chat: answers the user's questions about one check-in, from that check-in alone.

Question and answer only (plan.md §8.9): the chat explains the week and the proposals, turns
down medical and off-topic questions, and changes nothing. A change goes through the
proposal cards, as for any check-in.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from .graph import ask_agent, nutrition_context, output_limits, workout_context
from .metrics import RunMetrics, RunOutcome, elapsed_ms
from .model import CoachModel, ModelUnavailableError
from .schemas import ChatReply

if TYPE_CHECKING:
    from ..models import Proposal

logger = logging.getLogger(__name__)

# Earlier messages the model sees, oldest first: enough to follow up, little enough to stay cheap.
CHAT_HISTORY = 10
# A transient model error is tried once more; the user can always ask again.
CHAT_ATTEMPTS = 2
# The whole answer, retries included: the user is waiting, and the browser gives up at 35 s
# (frontend/src/api/coach-api.ts), so the server must have answered or failed before then.
CHAT_TIMEOUT_SECONDS = 25

CHAT_INSTRUCTIONS = f"""You are the coach in a fitness app, answering the user's questions about one
weekly check-in. You are given the week's figures, the proposals with their evidence and the
reviewer's note, and the conversation so far.

Use only those. If they don't answer the question, say what's missing; never invent numbers.
You can explain the week, the proposals and why they were made, and how the user's eating,
weight and training went. You can't change anything: to change a proposal the user edits or
rejects it on its card, and a new check-in can be started after another week of logging.

You are not a medical service. For injuries, pain, illness, medication, pregnancy or
disordered eating, say you can't advise on that, suggest a qualified professional, and set
topic to "medical". For anything outside nutrition and training, say briefly what you can
help with and set topic to "out_of_scope".

Answer in two to four short sentences, in plain words, in the language of the question.
{output_limits(ChatReply)}"""


def proposal_for_chat(proposal: Proposal) -> dict[str, Any]:
    return {
        "kind": proposal.kind.value,
        "headline": proposal.headline,
        "status": proposal.status.value,
        "proposed_changes": proposal.proposed_changes,
        "decided_changes": proposal.changes,
        "evidence": proposal.evidence,
        "reviewer_note": proposal.reviewer_note,
    }


def chat_context(
    snapshot: Mapping[str, Any],
    summary: str,
    proposals: Sequence[Mapping[str, Any]],
    history: Sequence[Mapping[str, str]],
    question: str,
) -> dict[str, Any]:
    """What the chat model sees: the same figures as the agents, never names or emails."""

    return {
        "week": {"summary": summary, **nutrition_context(snapshot), **workout_context(snapshot)},
        "proposals": list(proposals),
        "conversation": list(history[-CHAT_HISTORY:]),
        "question": question,
    }


async def answer_question(
    model: CoachModel, context: Mapping[str, Any], check_in_id: str
) -> ChatReply | None:
    """The coach's reply, or None when the model couldn't give one (it was down, timed out or
    kept answering outside the schema). Logged as ``coach chat answered``, with run metrics."""

    metrics = RunMetrics(model=model.name)
    started = time.monotonic()
    outcome: RunOutcome = "failed"
    error_name: str | None = None
    reply: ChatReply | None = None

    async def attempts() -> ChatReply | None:
        for attempt in range(1, CHAT_ATTEMPTS + 1):
            try:
                return await ask_agent(model, "chat", CHAT_INSTRUCTIONS, context, ChatReply, metrics)
            except ModelUnavailableError:
                if attempt == CHAT_ATTEMPTS:
                    raise
        return None

    try:
        reply = await asyncio.wait_for(attempts(), timeout=CHAT_TIMEOUT_SECONDS)
        outcome = "completed" if reply else "failed"
    except Exception as error:
        outcome = "timed_out" if isinstance(error, TimeoutError) else "failed"
        error_name = type(error).__name__
        logger.exception("coach chat failed", extra={"check_in_id": check_in_id})
    finally:
        logger.info(
            "coach chat answered",
            extra={
                "check_in_id": check_in_id,
                "topic": reply.topic if reply else None,
                "run_metrics": metrics.summary(
                    outcome=outcome, duration_ms=elapsed_ms(started), error=error_name
                ),
            },
        )
    return reply
