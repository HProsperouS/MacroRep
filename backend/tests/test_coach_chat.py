"""Coach Chat: answers about one check-in, from that check-in alone, and changes nothing."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.coach.agents.model import AgentTask, ModelReply, ModelUnavailableError
from app.demo_seed import DEMO_USER_EMAIL
from tests.fakes import ScriptedModel, use_model
from tests.helpers import (
    CHECK_INS,
    ask_coach,
    current_check_in,
    register_user,
    start_check_in,
    week_with_a_proposal,
)


def _messages(client: TestClient, headers: dict[str, str], check_in_id: str) -> list[dict]:
    response = client.get(f"{CHECK_INS}/{check_in_id}/messages", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_a_question_is_answered_from_the_check_in_and_kept(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    check_in = current_check_in(client, auth_headers)
    assert _messages(client, auth_headers, check_in["id"]) == []

    reply = ask_coach(client, auth_headers, check_in["id"], "Why this change?")

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
    check_in = current_check_in(client, auth_headers)
    reply = ask_coach(
        client, auth_headers, check_in["id"], "My knee has hurt since squats, what should I take?"
    )
    assert "can't advise" in reply.json()["text"]


def test_the_model_sees_the_week_proposals_and_conversation_but_no_personal_details(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedModel(chat={"intent": "explain", "reply": "Because your weight held steady."})
    use_model(monkeypatch, model)
    check_in = current_check_in(client, auth_headers)

    ask_coach(client, auth_headers, check_in["id"], "Why fewer calories?")
    ask_coach(client, auth_headers, check_in["id"], "And for how long?")

    first, second = (task.context for task in model.tasks)
    assert all(task.agent == "chat" for task in model.tasks)
    assert first["question"] == "Why fewer calories?" and first["conversation"] == []
    assert second["conversation"] == [
        {"role": "user", "text": "Why fewer calories?", "kind": "answer"},
        {"role": "coach", "text": "Because your weight held steady.", "kind": "answer"},
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
    model = ScriptedModel(chat={"intent": "explain", "reply": "Noted."})
    use_model(monkeypatch, model)
    check_in = current_check_in(client, auth_headers)
    for index in range(7):
        ask_coach(client, auth_headers, check_in["id"], f"Question {index}")

    conversation = model.tasks[-1].context["conversation"]
    assert len(conversation) == 10
    assert conversation[-2] == {"role": "user", "text": "Question 5", "kind": "answer"}


def test_no_answer_stores_nothing_and_says_try_again(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(task: AgentTask[Any]) -> dict[str, Any]:
        raise ModelUnavailableError("rate limited")

    model = ScriptedModel(chat=down)
    use_model(monkeypatch, model)
    check_in = current_check_in(client, auth_headers)

    reply = ask_coach(client, auth_headers, check_in["id"], "Why?")

    assert reply.status_code == 503
    assert "try again" in reply.json()["detail"]
    assert len(model.tasks) == 2, "a transient error is tried once more"
    assert _messages(client, auth_headers, check_in["id"]) == []


def test_an_answer_outside_the_schema_is_not_shown(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    use_model(monkeypatch, ScriptedModel(chat={"intent": "weather", "reply": "Sunny."}))
    check_in = current_check_in(client, auth_headers)
    assert ask_coach(client, auth_headers, check_in["id"], "Why?").status_code == 503
    assert _messages(client, auth_headers, check_in["id"]) == []


def test_another_users_conversation_is_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    check_in = current_check_in(client, auth_headers)
    ask_coach(client, auth_headers, check_in["id"], "Why?")
    stranger = register_user(client)

    assert client.get(f"{CHECK_INS}/{check_in['id']}/messages", headers=stranger).status_code == 404
    assert ask_coach(client, stranger, check_in["id"], "Why?").status_code == 404


def test_questions_wait_until_the_check_in_is_ready(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = register_user(client)
    week_with_a_proposal(client, headers)

    async def never_runs(_: str) -> None:
        return None

    monkeypatch.setattr("app.coach.router.generate_check_in", never_runs)
    check_in = start_check_in(client, headers, "chat-early").json()

    response = ask_coach(client, headers, check_in["id"], "Why?")
    assert response.status_code == 409
    assert "once the check-in is ready" in response.json()["detail"]


def test_each_answer_is_logged_with_its_intent_and_cost(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    use_model(
        monkeypatch,
        ScriptedModel(chat={"intent": "out_of_scope", "reply": "I can help with food and training."}),
    )
    caplog.set_level("INFO", logger="app.coach.agents.chat")
    check_in = current_check_in(client, auth_headers)

    ask_coach(client, auth_headers, check_in["id"], "Write me a poem")

    [record] = [r for r in caplog.records if r.message == "coach chat answered"]
    assert record.intent == "out_of_scope"  # type: ignore[attr-defined]
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
            return ModelReply({"intent": "explain", "reply": "Too late."})

    assert chat.CHAT_TIMEOUT_SECONDS < 35, "the browser waits 35 s for an answer"
    monkeypatch.setattr(chat, "CHAT_TIMEOUT_SECONDS", 0.1)
    use_model(monkeypatch, SlowModel())
    caplog.set_level("INFO", logger="app.coach.agents.chat")
    check_in = current_check_in(client, auth_headers)

    assert ask_coach(client, auth_headers, check_in["id"], "Why?").status_code == 503
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

    check_in = current_check_in(client, auth_headers)
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


def test_questions_per_user_are_limited_unanswered_ones_excepted(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.shared.rate_limit import CHAT_QUESTIONS_PER_USER

    def down(task: AgentTask[Any]) -> dict[str, Any]:
        raise ModelUnavailableError("rate limited")

    check_in = current_check_in(client, auth_headers)
    assert (
        ask_coach(client, auth_headers, "no-such-check-in", "Why?").status_code == 404
    )  # not counted: no model call
    with monkeypatch.context() as patch:
        use_model(patch, ScriptedModel(chat=down))
        for _ in range(3):  # our failure, not counted
            assert ask_coach(client, auth_headers, check_in["id"], "Why?").status_code == 503
    for _ in range(CHAT_QUESTIONS_PER_USER.attempts):
        assert ask_coach(client, auth_headers, check_in["id"], "Why?").status_code == 200

    refused = ask_coach(client, auth_headers, check_in["id"], "Why?")

    assert refused.status_code == 429
    assert refused.json()["detail"].startswith("That's a lot of questions for now. Try again in")
    other_user = register_user(client)
    week_with_a_proposal(client, other_user)
    assert (
        ask_coach(
            client, other_user, start_check_in(client, other_user, "k").json()["id"], "Why?"
        ).status_code
        == 200
    )


def test_switched_off_questions_are_not_limited(client: TestClient, auth_headers: dict[str, str]) -> None:
    from app.core.config import get_settings
    from app.main import app
    from app.shared.rate_limit import CHAT_QUESTIONS_PER_USER, user_limiter

    settings = get_settings().model_copy(update={"rate_limits_enabled": False})
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        check_in = current_check_in(client, auth_headers)
        for _ in range(CHAT_QUESTIONS_PER_USER.attempts + 1):
            assert ask_coach(client, auth_headers, check_in["id"], "Why?").status_code == 200
    finally:
        app.dependency_overrides.pop(get_settings)
    assert user_limiter._hits == {}  # noqa: SLF001


def test_a_flood_of_sign_ins_cant_reset_a_users_question_count(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.shared import rate_limit

    monkeypatch.setattr(rate_limit, "_MAX_KEYS", 3)
    rate_limit.user_limiter.hit(("chat", "user-1"), rate_limit.CHAT_QUESTIONS_PER_USER)
    for index in range(10):
        rate_limit.limiter.hit(("login", f"10.0.0.{index}"), rate_limit.LOGINS_PER_ADDRESS)

    assert ("chat", "user-1") in rate_limit.user_limiter._hits  # noqa: SLF001
