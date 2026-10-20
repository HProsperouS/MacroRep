"""What one check-in run cost: time, model calls, retries and tokens, per agent and in total.

``_ask`` records every model call, including the ones LangGraph retries and the second try
after an answer that doesn't fit the schema. ``summary`` is logged when the run ends, as
``check-in run finished`` (kept in the daily log files when ``LOG_DIR`` is set).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

CallOutcome = Literal["valid", "invalid", "error"]
# "discarded": the run finished, but its check-in had already been failed or finished by
# another run, so nothing was stored. "interrupted": stopped at shutdown, to be resumed.
RunOutcome = Literal["completed", "discarded", "failed", "timed_out", "interrupted"]


def elapsed_ms(started: float) -> int:
    """Milliseconds since ``started``, a ``time.monotonic()`` reading."""

    return round((time.monotonic() - started) * 1000)


@dataclass(frozen=True)
class ModelCall:
    agent: str
    duration_ms: int
    outcome: CallOutcome
    # The exception's class name for an "error"; never its message, which may echo input.
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class RunMetrics:
    model: str
    # Continued from a checkpoint: agents finished before the interruption aren't counted.
    resumed: bool = False
    calls: list[ModelCall] = field(default_factory=list)

    def add(
        self,
        agent: str,
        started: float,
        outcome: CallOutcome,
        *,
        error: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        self.calls.append(ModelCall(agent, elapsed_ms(started), outcome, error, input_tokens, output_tokens))

    def summary(self, *, outcome: RunOutcome, duration_ms: int, error: str | None = None) -> dict[str, Any]:
        agents: dict[str, dict[str, Any]] = {}
        for call in self.calls:
            agent = agents.setdefault(
                call.agent,
                {
                    "calls": 0,
                    "duration_ms": 0,
                    "outcome": None,
                    "errors": [],
                    "input_tokens": 0,
                    "output_tokens": 0,
                },
            )
            agent["calls"] += 1
            agent["duration_ms"] += call.duration_ms
            agent["outcome"] = call.outcome  # the last call decides
            agent["input_tokens"] += call.input_tokens
            agent["output_tokens"] += call.output_tokens
            if call.error is not None:
                agent["errors"].append(call.error)
        return {
            "outcome": outcome,
            "error": error,
            "duration_ms": duration_ms,
            "model": self.model,
            "resumed": self.resumed,
            "calls": len(self.calls),
            "input_tokens": sum(call.input_tokens for call in self.calls),
            "output_tokens": sum(call.output_tokens for call in self.calls),
            "agents": agents,
        }
