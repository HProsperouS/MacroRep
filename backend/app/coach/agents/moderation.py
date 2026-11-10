"""Screening a Coach Chat message before the paid model sees it.

OpenAI's moderation endpoint (free) says whether text is harmful: self-harm, violence, hate,
sexual content, harassment. A flagged message gets a fixed reply and never reaches the
coach. It doesn't judge whether a message is on topic; the coach's own intents and the fixed
refusals (coach/chat.py) do that.

Fails open: if moderation can't answer, the message goes on to the coach, which keeps its
topic rules, fixed refusals and output caps. A moderation outage shouldn't take the chat down.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

import openai

logger = logging.getLogger(__name__)

MODERATION_MODEL = "omni-moderation-latest"
# Moderation is quick; the chat's own time limit starts after it (agents/chat.py).
MODERATION_TIMEOUT_SECONDS = 5


class Moderator(Protocol):
    async def flagged(self, text: str) -> bool | None:
        """Whether ``text`` is harmful, or None when it couldn't be checked."""
        ...


class NoModerator:
    """Lets everything through: with the rule-based model and in local development."""

    async def flagged(self, text: str) -> bool | None:
        return False


class OpenAIModerator:
    def __init__(self, client: openai.AsyncOpenAI) -> None:
        self.client = client

    async def flagged(self, text: str) -> bool | None:
        try:
            result = await asyncio.wait_for(
                self.client.moderations.create(model=MODERATION_MODEL, input=text),
                MODERATION_TIMEOUT_SECONDS,
            )
            return bool(result.results[0].flagged)
        except (openai.OpenAIError, TimeoutError, IndexError) as error:
            logger.warning("coach chat moderation unavailable", extra={"error": type(error).__name__})
            return None
