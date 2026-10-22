"""The seam between the agents and a language model.

An agent hands the model an ``AgentTask``: its role, its instructions, a compact
JSON context, and the output schema. The model answers with raw structured output,
which the caller validates against the schema; a model can't skip validation.

Two models implement ``CoachModel``: ``FakeCoachModel`` (fake_model.py), a deterministic
stand-in so the whole flow runs and is testable without an API key, and ``OpenAICoachModel``
(openai_model.py). ``get_coach_model`` (provider.py) picks one by ``COACH_MODEL_PROVIDER``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
AgentName = Literal["nutrition", "workout", "reviewer", "chat", "food_photo"]


class ModelUnavailableError(Exception):
    """A transient failure talking to the model (timeout, rate limit, 5xx): worth retrying."""


@dataclass(frozen=True)
class AgentTask(Generic[T]):
    agent: AgentName
    instructions: str
    context: Mapping[str, Any]
    output: type[T]
    # Images for the model to look at, as data: URLs (only the food-photo estimate sends one).
    images: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelReply:
    """Raw output, with the tokens it took when the provider reports them."""

    output: Mapping[str, Any] | str
    input_tokens: int = 0
    output_tokens: int = 0


class CoachModel(Protocol):
    # Recorded with each run, e.g. "fake" or "openai/gpt-5.4-mini".
    name: str

    async def generate(self, task: AgentTask[T]) -> ModelReply:
        """Raw structured output for ``task`` (a JSON object, or JSON text) and its tokens."""
        ...
