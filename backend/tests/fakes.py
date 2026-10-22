"""A scripted stand-in for the coach model, shared by the agent, chat, revision and photo tests."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any

import pytest

from app.coach.agents.model import AgentTask, ModelReply

# A reply (a JSON object, or text), a function of the task giving one, or an error to raise.
Answer = Mapping[str, Any] | str | Callable[[AgentTask[Any]], Any] | BaseException | type[BaseException]


class ScriptedModel:
    """Answers each agent from its script: one answer for every call, or a list used one per call
    (the last repeating). Keeps every task it's given."""

    name = "scripted"

    def __init__(self, **script: Answer | list[Answer]) -> None:
        self.script = script
        self.tasks: list[AgentTask[Any]] = []

    @property
    def agents(self) -> list[str]:
        """The agents asked, in order."""

        return [task.agent for task in self.tasks]

    @property
    def calls(self) -> dict[str, list[Mapping[str, Any]]]:
        """The context each agent was given, per call."""

        seen: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for task in self.tasks:
            seen[task.agent].append(task.context)
        return seen

    async def generate(self, task: AgentTask[Any]) -> ModelReply:
        self.tasks.append(task)
        answers = self.script[task.agent]
        if isinstance(answers, list):
            assert answers, f"no answers scripted for {task.agent}"
            answer = answers[min(self.agents.count(task.agent), len(answers)) - 1]
        else:
            answer = answers
        if isinstance(answer, BaseException):
            raise answer
        if isinstance(answer, type):  # an error class, raised as is
            raise answer
        if isinstance(answer, Mapping | str):
            return ModelReply(answer)
        return ModelReply(answer(task))


def use_model(monkeypatch: pytest.MonkeyPatch, model: Any) -> None:
    """Make the app use ``model`` for check-ins, Coach Chat and meal photos."""

    monkeypatch.setattr("app.coach.factory.get_coach_model", lambda: model)
    monkeypatch.setattr("app.food.router.get_coach_model", lambda: model)
