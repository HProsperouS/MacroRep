"""Coach Chat: answers about one check-in, from that check-in alone, and changes nothing."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.coach.agents.model import AgentTask, ModelReply, ModelUnavailableError
from app.demo_seed import DEMO_USER_EMAIL
from tests.helpers import register_user
from tests.test_coach_api import CHECK_INS, _start, _week_with_a_proposal


class RecordingModel:
    """Answers chat with ``answer`` (a reply, or a function of the task) and keeps every task."""

    name = "recording"

    def __init__(self, answer: dict[str, Any] | Callable[[AgentTask[Any]], dict[str, Any]]) -> None:
        self.answer = answer
        self.tasks: list[AgentTask[Any]] = []

    async def generate(self, task: AgentTask[Any]) -> ModelReply:
        self.tasks.append(task)
        return ModelReply(self.answer(task) if callable(self.answer) else self.answer)


def _use(monkeypatch: pytest.MonkeyPatch, model: Any) -> None:
    monkeypatch.setattr("app.coach.service.get_coach_model", lambda: model)


def _current(client: TestClient, headers: dict[str, str]) -> dict:
    return client.get(f"{CHECK_INS}/current", headers=headers).json()


def _ask(client: TestClient, headers: dict[str, str], check_in_id: str, text: str):
    return client.post(f"{CHECK_INS}/{check_in_id}/messages", headers=headers, json={"text": text})


def _messages(client: TestClient, headers: dict[str, str], check_in_id: str) -> list[dict]:
    response = client.get(f"{CHECK_INS}/{check_in_id}/messages", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_a_question_is_answered_from_the_check_in_and_kept(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    check_in = _current(client, auth_headers)
    assert _messages(client, auth_headers, check_in["id"]) == []

    reply = _ask(client, auth_headers, check_in["id"], "Why this change?")

    assert reply.status_code == 200
    assert reply.json()["role"] == "coach"
    assert check_in["proposals"][0]["headline"] in reply.json()["text"], (
        "the rule-based coach quotes the proposal"
    )
    assert [(m["role"], m["text"]) for m in _messages(client, auth_headers, check_in["id"])] == [
        ("user", "Why this change?"),
        ("coach", reply.json()["text"]),
    ]


def test_a_medical_question_is_turned_down(client: TestClient, auth_headers: dict[str, str]) -> None:
    check_in = _current(client, auth_headers)
    reply = _ask(client, auth_headers, check_in["id"], "My knee has hurt since squats, what should I take?")
    assert "can't advise" in reply.json()["text"]


def test_the_model_sees_the_week_proposals_and_conversation_but_no_personal_details(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = RecordingModel({"topic": "check_in", "reply": "Because your weight held steady."})
    _use(monkeypatch, model)
    check_in = _current(client, auth_headers)

    _ask(client, auth_headers, check_in["id"], "Why fewer calories?")
    _ask(client, auth_headers, check_in["id"], "And for how long?")

    first, second = (task.context for task in model.tasks)
    assert all(task.agent == "chat" for task in model.tasks)
    assert first["question"] == "Why fewer calories?" and first["conversation"] == []
    assert second["conversation"] == [
        {"role": "user", "text": "Why fewer calories?"},
        {"role": "coach", "text": "Because your weight held steady."},
    ]
    assert first["week"]["target_calories"] and first["week"]["summary"] == check_in["summary"]
    [proposal] = first["proposals"]
    assert (proposal["headline"], proposal["status"]) == (check_in["proposals"][0]["headline"], "pending")
    assert proposal["evidence"] and "proposed_changes" in proposal
    sent = json.dumps(first)
    assert DEMO_USER_EMAIL not in sent and "Alex" not in sent


def test_only_the_latest_messages_are_sent(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = RecordingModel({"topic": "progress", "reply": "Noted."})
    _use(monkeypatch, model)
    check_in = _current(client, auth_headers)
    for index in range(7):
        _ask(client, auth_headers, check_in["id"], f"Question {index}")

    conversation = model.tasks[-1].context["conversation"]
    assert len(conversation) == 10
    assert conversation[-2] == {"role": "user", "text": "Question 5"}


def test_no_answer_stores_nothing_and_says_try_again(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(task: AgentTask[Any]) -> dict[str, Any]:
        raise ModelUnavailableError("rate limited")

    model = RecordingModel(down)
    _use(monkeypatch, model)
    check_in = _current(client, auth_headers)

    reply = _ask(client, auth_headers, check_in["id"], "Why?")

    assert reply.status_code == 503
    assert "try again" in reply.json()["detail"]
    assert len(model.tasks) == 2, "a transient error is tried once more"
    assert _messages(client, auth_headers, check_in["id"]) == []


def test_an_answer_outside_the_schema_is_not_shown(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, RecordingModel({"topic": "weather", "reply": "Sunny."}))
    check_in = _current(client, auth_headers)
    assert _ask(client, auth_headers, check_in["id"], "Why?").status_code == 503
    assert _messages(client, auth_headers, check_in["id"]) == []


def test_another_users_conversation_is_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    check_in = _current(client, auth_headers)
    _ask(client, auth_headers, check_in["id"], "Why?")
    stranger = register_user(client)

    assert client.get(f"{CHECK_INS}/{check_in['id']}/messages", headers=stranger).status_code == 404
    assert _ask(client, stranger, check_in["id"], "Why?").status_code == 404


def test_questions_wait_until_the_check_in_is_ready(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = register_user(client)
    _week_with_a_proposal(client, headers)

    async def never_runs(_: str) -> None:
        return None

    monkeypatch.setattr("app.coach.router.generate_check_in", never_runs)
    check_in = _start(client, headers, "chat-early").json()

    response = _ask(client, headers, check_in["id"], "Why?")
    assert response.status_code == 409
    assert "once the check-in is ready" in response.json()["detail"]


def test_each_answer_is_logged_with_its_topic_and_cost(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _use(
        monkeypatch, RecordingModel({"topic": "out_of_scope", "reply": "I can help with food and training."})
    )
    caplog.set_level("INFO", logger="app.coach.agents.chat")
    check_in = _current(client, auth_headers)

    _ask(client, auth_headers, check_in["id"], "Write me a poem")

    [record] = [r for r in caplog.records if r.message == "coach chat answered"]
    assert record.topic == "out_of_scope"  # type: ignore[attr-defined]
    assert record.run_metrics["outcome"] == "completed" and record.run_metrics["calls"] == 1  # type: ignore[attr-defined]


def test_a_slow_model_is_given_up_on_before_the_browser_gives_up(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.coach.agents import chat

    class SlowModel:
        name = "slow"

        async def generate(self, task: AgentTask[Any]) -> ModelReply:
            await asyncio.sleep(1)
            return ModelReply({"topic": "progress", "reply": "Too late."})

    assert chat.CHAT_TIMEOUT_SECONDS < 35, "the browser waits 35 s for an answer"
    monkeypatch.setattr(chat, "CHAT_TIMEOUT_SECONDS", 0.1)
    _use(monkeypatch, SlowModel())
    caplog.set_level("INFO", logger="app.coach.agents.chat")
    check_in = _current(client, auth_headers)

    assert _ask(client, auth_headers, check_in["id"], "Why?").status_code == 503
    assert _messages(client, auth_headers, check_in["id"]) == []
    [record] = [r for r in caplog.records if r.message == "coach chat answered"]
    assert record.run_metrics["outcome"] == "timed_out"  # type: ignore[attr-defined]


def test_a_question_comes_before_its_answer_even_when_saved_at_the_same_instant(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from datetime import UTC, datetime

    from app.coach.models import CoachMessage, MessageRole
    from app.coach.repository import CoachRepository
    from app.core.database import get_session_factory
    from app.demo_seed import DEMO_USER_ID

    check_in = _current(client, auth_headers)
    instant = datetime(2026, 10, 20, 9, tzinfo=UTC)

    async def save() -> None:
        async with get_session_factory()() as session:
            repository = CoachRepository(session)
            for role, text in ((MessageRole.COACH, "Answer"), (MessageRole.USER, "Question")):
                await repository.add_message(
                    CoachMessage(
                        check_in_id=check_in["id"],
                        owner_id=DEMO_USER_ID,
                        role=role,
                        text=text,
                        created_utc=instant,
                    )
                )
            await session.commit()

    assert client.portal is not None
    client.portal.call(save)
    assert [m["text"] for m in _messages(client, auth_headers, check_in["id"])] == ["Question", "Answer"]
