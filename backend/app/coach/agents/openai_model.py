"""``CoachModel`` on OpenAI's Chat Completions API."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

import openai
from openai.types.shared import ReasoningEffort

from .model import AgentTask, ModelReply, ModelUnavailableError, T

logger = logging.getLogger(__name__)


class OpenAICoachModel:
    """Asks OpenAI's Chat Completions API for an answer in the task's output schema.

    The schema is sent non-strict: strict mode accepts only a subset of JSON Schema, and the
    caller validates every answer against the full schema anyway.
    """

    def __init__(
        self, client: openai.AsyncOpenAI, model: str, reasoning_effort: ReasoningEffort = None
    ) -> None:
        self.client = client
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.name = f"openai/{model}"

    async def generate(self, task: AgentTask[T]) -> ModelReply:
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": task.instructions},
                    {"role": "user", "content": _user_content(task)},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": task.output.__name__,
                        "schema": task.output.model_json_schema(),
                        "strict": False,
                    },
                },
                # Omitted, not sent as null, for a model without reasoning.
                reasoning_effort=self.reasoning_effort or openai.omit,
            )
        # A timeout is a connection error too.
        except openai.APIConnectionError as error:
            raise ModelUnavailableError(type(error).__name__) from error
        except openai.APIStatusError as error:
            # The statuses the SDK itself would retry. Anything else (a bad key, a bad request)
            # won't get better by asking again, so it fails the run.
            if error.status_code in _RETRYABLE_STATUSES or error.status_code >= 500:
                raise ModelUnavailableError(f"HTTP {error.status_code}") from error
            raise
        choice = completion.choices[0]
        if choice.finish_reason != "stop" or choice.message.refusal:
            # Cut off or refused: it is rejected like any answer that doesn't fit the schema.
            logger.warning(
                "model answer incomplete",
                extra={
                    "agent": task.agent,
                    "finish_reason": choice.finish_reason,
                    "refused": bool(choice.message.refusal),
                },
            )
        usage = completion.usage
        return ModelReply(
            output=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


def _user_content(task: AgentTask[Any]) -> Any:
    """The context as JSON, followed by any images."""

    text = json.dumps(task.context, default=str)
    if not task.images:
        return text
    return [
        {"type": "text", "text": text},
        *({"type": "image_url", "image_url": {"url": image}} for image in task.images),
    ]


_RETRYABLE_STATUSES = frozenset({408, 409, 429})


@lru_cache(maxsize=1)
def cached_openai_model(
    api_key: str, model: str, timeout_seconds: float, reasoning_effort: ReasoningEffort
) -> OpenAICoachModel:
    """One client per configuration, so its connection pool is reused across check-ins."""

    # The client doesn't retry: the callers do, within their own time limits (LangGraph's retry
    # policy for check-in steps, ask_with_retry for chat and photos).
    client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)
    return OpenAICoachModel(client, model, reasoning_effort)
