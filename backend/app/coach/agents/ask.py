"""Asking one agent for an answer in its output schema, and running a call on its own.

``ask_agent`` is the one place a model is called: the check-in graph, Coach Chat, revisions
and meal photos all go through it, so every call is validated and counted the same way.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar, get_args, get_origin

from annotated_types import MaxLen
from pydantic import BaseModel, ValidationError

from .metrics import RunMetrics, RunOutcome, elapsed_ms
from .model import AgentName, AgentTask, CoachModel, ModelUnavailableError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")

# One more try after an answer that doesn't parse; past that, retrying rarely helps.
STRUCTURED_OUTPUT_ATTEMPTS = 2


def _length_limits(schema: type[BaseModel], owner: str = "") -> list[str]:
    """The schema's length limits, in words: the model isn't held to them while generating."""

    found: list[str] = []
    for name, field in schema.model_fields.items():
        label = f"{owner}{name}"
        limit = next((m.max_length for m in field.metadata if isinstance(m, MaxLen)), None)
        if get_origin(field.annotation) is list:
            if limit is not None:
                found.append(f"at most {limit} {label} items")
            [item] = get_args(field.annotation)
            if isinstance(item, type) and issubclass(item, BaseModel):
                found += _length_limits(item, f"each {name} item's ")
        elif limit is not None:
            found.append(f"{label} under {limit} characters")
    return found


def output_limits(schema: type[BaseModel]) -> str:
    return f"Stay within these limits: {'; '.join(_length_limits(schema))}."


async def ask_agent(
    model: CoachModel,
    agent: AgentName,
    instructions: str,
    context: Mapping[str, Any],
    output: type[T],
    metrics: RunMetrics,
    images: tuple[str, ...] = (),
) -> T | None:
    """The agent's validated answer, or None if it never produced one that fits the schema.
    Every model call is added to ``metrics``, including one that fails."""

    task = AgentTask(agent=agent, instructions=instructions, context=context, output=output, images=images)
    for attempt in range(1, STRUCTURED_OUTPUT_ATTEMPTS + 1):
        started = time.monotonic()
        try:
            reply = await model.generate(task)
        except BaseException as error:  # also a cancelled call, when the step runs out of time
            metrics.add(agent, started, "error", error=type(error).__name__)
            raise
        raw = reply.output
        try:
            parsed = output.model_validate_json(raw) if isinstance(raw, str) else output.model_validate(raw)
        except ValidationError:
            parsed = None
            logger.warning("agent output rejected", extra={"agent": agent, "attempt": attempt})
        metrics.add(
            agent,
            started,
            "invalid" if parsed is None else "valid",
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
        )
        if parsed is not None:
            return parsed
    return None


async def ask_with_retry(
    model: CoachModel,
    agent: AgentName,
    instructions: str,
    context: Mapping[str, Any],
    output: type[T],
    metrics: RunMetrics,
    *,
    attempts: int,
    retry_within_seconds: float | None = None,
    images: tuple[str, ...] = (),
) -> T | None:
    """``ask_agent``, asked again when the model is briefly unavailable, up to ``attempts`` times
    in all (at least once). With ``retry_within_seconds``, a retry that would start later than
    that isn't made: it wouldn't finish in time."""

    started = time.monotonic()
    for _ in range(attempts - 1):
        try:
            return await ask_agent(model, agent, instructions, context, output, metrics, images)
        except ModelUnavailableError:
            if retry_within_seconds is not None and elapsed_ms(started) > retry_within_seconds * 1000:
                raise
    return await ask_agent(model, agent, instructions, context, output, metrics, images)


async def logged_run(
    work: Awaitable[R | None],
    *,
    metrics: RunMetrics,
    timeout_seconds: float,
    log: logging.Logger,
    event: str,
    failure_event: str,
    extra: Mapping[str, Any],
    details: Callable[[R | None], Mapping[str, Any]],
    succeeded: Callable[[R | None], bool] = lambda result: result is not None,
) -> R | None:
    """``work``'s result, or None when it failed or ran out of time. Either way it's logged as
    ``event``, with ``extra``, ``details`` of the result and the run's metrics; a failure is
    logged as ``failure_event`` too."""

    started = time.monotonic()
    outcome: RunOutcome = "failed"
    error_name: str | None = None
    result: R | None = None
    try:
        result = await asyncio.wait_for(work, timeout=timeout_seconds)
        outcome = "completed" if succeeded(result) else "failed"
    except Exception as error:
        outcome = "timed_out" if isinstance(error, TimeoutError) else "failed"
        error_name = type(error).__name__
        log.exception(failure_event, extra=dict(extra))
    finally:
        summary = metrics.summary(outcome=outcome, duration_ms=elapsed_ms(started), error=error_name)
        log.info(event, extra={**extra, **details(result), "run_metrics": summary})
    return result
