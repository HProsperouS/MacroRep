"""Coach Chat about one check-in, from that check-in alone (plan.md §8.9, §9.9).

Each turn first works out what the user wants. A question is answered; a medical or
off-topic one is turned down. A change to a proposal, once clear enough (one clarifying
question at a time, at most ``MAX_CLARIFICATIONS``), is handed to ``revise.py``, whose result
is a pending proposal the user applies on its card: the chat never changes anything itself.
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
from .revise import ProposalKindName, Revision, revise
from .schemas import ChatReply

if TYPE_CHECKING:
    from ..models import Proposal

logger = logging.getLogger(__name__)

# Earlier messages the model sees, oldest first: enough to follow up, little enough to stay cheap.
CHAT_HISTORY = 10
# A transient model error is tried once more; the user can always ask again.
CHAT_ATTEMPTS = 2
# Each step, retries included: working out the request, then revising a proposal (two or
# three model calls). The browser gives up at 60 s (frontend/src/api/coach-api.ts), so
# both together must have answered or failed before then.
CHAT_TIMEOUT_SECONDS = 25
REVISION_TIMEOUT_SECONDS = 25
# Clarifying questions in a row before the coach stops asking and says what it can do.
MAX_CLARIFICATIONS = 2
STOP_ASKING = (
    "I still can't tell what change you'd like. You could say, for example, "
    "\u201cRaise my calorie target by 100 kcal\u201d or \u201cKeep bench press at its current weight\u201d, "
    "or change the values yourself with Edit on the proposal card."
)

CHAT_INSTRUCTIONS = f"""You are the coach in a fitness app, talking with the user about one weekly
check-in. You are given the week's figures, the proposals with their evidence and the
reviewer's note, and the conversation so far. First decide what the user wants (intent):

- "explain": a question about the week, the proposals or their progress. Answer it from the
  figures only; if they don't answer it, say what's missing. Never invent numbers.
- "adjust_nutrition": they want the calorie target proposal changed (more, less, kept).
- "adjust_workout": they want a training change for an exercise changed (load, sets, reps).
  For either: if they said clearly enough what to change (the direction, and for training
  which exercise; read the conversation, an earlier message may have said it), set request
  to that change in one plain English sentence, e.g. "Cut calories by about 100 kcal instead
  of 200" or "Keep bench press at its current weight", and reply with a short
  acknowledgement. If not, leave request empty and reply with one short question about the
  single most important missing detail. Don't guess a detail that would change the result:
  "change my calories" or "adjust my workout" says no direction, so ask, and the current
  proposal is never the user's request.
  You never change anything yourself: the request becomes a revised proposal that the user
  applies on its card, after the same checks as any check-in.
- "start_check_in": they want a new check-in. Say it's started with the button at the top of
  the page once another week is logged.
- "medical": injuries, pain, illness, medication, pregnancy or disordered eating. Say you
  can't advise on that and suggest a qualified professional.
- "out_of_scope": anything else outside nutrition and training. Say briefly what you can
  help with.

Reply in two to four short sentences, in plain words, in the language of the user's message.
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


def clarifications_in_a_row(history: Sequence[Mapping[str, str]]) -> int:
    """How many of the coach's latest messages, back to its last other kind, asked a question."""

    count = 0
    for message in reversed(history):
        if message["role"] != "coach":
            continue
        if message.get("kind") != "clarification":
            break
        count += 1
    return count


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
                "intent": reply.intent if reply else None,
                "run_metrics": metrics.summary(
                    outcome=outcome, duration_ms=elapsed_ms(started), error=error_name
                ),
            },
        )
    return reply


async def revise_proposal(
    model: CoachModel,
    kind: ProposalKindName,
    snapshot: Mapping[str, Any],
    request: str,
    current: Mapping[str, Any] | None,
    other_changes: Sequence[Mapping[str, Any]] | None,
    check_in_id: str,
) -> Revision | None:
    """The revision, or None when the model couldn't give one in time. Logged as
    ``coach chat revised``, with run metrics."""

    metrics = RunMetrics(model=model.name)
    started = time.monotonic()
    outcome: RunOutcome = "failed"
    error_name: str | None = None
    revision: Revision | None = None
    try:
        revision = await asyncio.wait_for(
            revise(model, metrics, kind, snapshot, request, current, other_changes),
            timeout=REVISION_TIMEOUT_SECONDS,
        )
        outcome = "completed"
    except Exception as error:
        outcome = "timed_out" if isinstance(error, TimeoutError) else "failed"
        error_name = type(error).__name__
        logger.exception("coach chat revision failed", extra={"check_in_id": check_in_id})
    finally:
        logger.info(
            "coach chat revised",
            extra={
                "check_in_id": check_in_id,
                "kind": kind,
                "revised": bool(revision and revision.draft),
                "run_metrics": metrics.summary(
                    outcome=outcome, duration_ms=elapsed_ms(started), error=error_name
                ),
            },
        )
    return revision
