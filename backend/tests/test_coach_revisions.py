"""Coach Chat working out what the user wants, asking when it's unclear, and revising a
proposal on request through the same checks as a check-in."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.coach.agents.chat import STOP_ASKING
from app.coach.agents.model import AgentTask, ModelReply, ModelUnavailableError
from app.coach.models import ProposalKind
from app.coach.service import ALREADY_APPLIED
from tests.helpers import register_user
from tests.test_coach_api import CHECK_INS, _training_check_in


class ScriptedModel:
    """Answers each agent with its entry in ``answers`` (a reply, or a function of the task)."""

    name = "scripted"

    def __init__(self, **answers: dict[str, Any] | Callable[[AgentTask[Any]], dict[str, Any]]) -> None:
        self.answers = answers
        self.agents: list[str] = []

    async def generate(self, task: AgentTask[Any]) -> ModelReply:
        self.agents.append(task.agent)
        answer = self.answers[task.agent]
        return ModelReply(answer(task) if callable(answer) else answer)


def _use(monkeypatch: pytest.MonkeyPatch, model: Any) -> None:
    monkeypatch.setattr("app.coach.service.get_coach_model", lambda: model)


def _current(client: TestClient, headers: dict[str, str]) -> dict:
    return client.get(f"{CHECK_INS}/current", headers=headers).json()


def _ask(client: TestClient, headers: dict[str, str], check_in_id: str, text: str) -> dict:
    response = client.post(f"{CHECK_INS}/{check_in_id}/messages", headers=headers, json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def _nutrition(check_in: dict) -> dict:
    return [p for p in check_in["proposals"] if p["kind"] == "nutrition"][-1]


def test_an_unclear_change_gets_one_question_then_the_answer_revises_the_proposal(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    check_in = _current(client, auth_headers)
    before = _nutrition(check_in)

    question = _ask(client, auth_headers, check_in["id"], "Can you change my calories?")
    assert (question["kind"], question["text"]) == (
        "clarification",
        "More or fewer calories, and by about how much?",
    )
    assert _nutrition(_current(client, auth_headers)) == before, "nothing changes while asking"

    done = _ask(client, auth_headers, check_in["id"], "A bit more calories please")

    assert done["kind"] == "revision"
    after = _nutrition(_current(client, auth_headers))
    assert after["id"] == before["id"] and after["status"] == "pending", "the same card, still to apply"
    assert after["changes"][0]["after"] == 2350 + 100, (
        "the rule-based agent's step, from the check-in's target"
    )
    assert after["proposedChanges"] == after["changes"]
    assert after["reviewerNote"].startswith("Revised at your request.")


def test_the_replaced_version_is_kept(client: TestClient, auth_headers: dict[str, str]) -> None:
    from app.coach.models import Proposal
    from app.core.database import get_session_factory

    check_in = _current(client, auth_headers)
    before = _nutrition(check_in)
    _ask(client, auth_headers, check_in["id"], "Fewer calories please")

    async def revisions() -> list[dict]:
        async with get_session_factory()() as session:
            proposal = await session.get(Proposal, before["id"])
            assert proposal is not None
            return proposal.revisions

    assert client.portal is not None
    [kept] = client.portal.call(revisions)
    assert (kept["headline"], kept["proposed_changes"][0]["after"]) == (
        before["headline"],
        before["changes"][0]["after"],
    )
    assert kept["request"] == "Fewer calories please" and kept["replaced_utc"]


def test_the_coach_stops_asking_after_two_questions(client: TestClient, auth_headers: dict[str, str]) -> None:
    check_in = _current(client, auth_headers)
    kinds = [_ask(client, auth_headers, check_in["id"], "Change my calories")["kind"] for _ in range(2)]
    last = _ask(client, auth_headers, check_in["id"], "Change my calories")

    assert kinds == ["clarification", "clarification"]
    assert (last["kind"], last["text"]) == ("answer", STOP_ASKING)


def test_an_applied_change_is_left_alone(client: TestClient, auth_headers: dict[str, str]) -> None:
    check_in = _current(client, auth_headers)
    proposal = _nutrition(check_in)
    client.post(
        f"{CHECK_INS}/{check_in['id']}/proposals/{proposal['id']}/decision",
        headers=auth_headers,
        json={"decision": "apply"},
    )

    reply = _ask(client, auth_headers, check_in["id"], "Fewer calories please")

    assert (reply["kind"], reply["text"]) == ("answer", ALREADY_APPLIED[ProposalKind.NUTRITION])
    assert _nutrition(_current(client, auth_headers))["status"] == "applied"


def test_after_a_rejection_a_new_proposal_is_made(client: TestClient, auth_headers: dict[str, str]) -> None:
    check_in = _current(client, auth_headers)
    rejected = _nutrition(check_in)
    client.post(
        f"{CHECK_INS}/{check_in['id']}/proposals/{rejected['id']}/decision",
        headers=auth_headers,
        json={"decision": "reject"},
    )

    assert _ask(client, auth_headers, check_in["id"], "Fewer calories please")["kind"] == "revision"

    after = _current(client, auth_headers)
    statuses = [p["status"] for p in after["proposals"] if p["kind"] == "nutrition"]
    assert statuses == ["rejected", "pending"]
    assert after["status"] == "needs-review"


def test_a_training_change_is_revised_for_the_lift_named(client: TestClient) -> None:
    headers = register_user(client)
    routine, check_in = _training_check_in(client, headers)

    reply = _ask(client, headers, check_in["id"], "Make barbell bench press heavier")

    assert reply["kind"] == "revision"
    training = [p for p in _current(client, headers)["proposals"] if p["kind"] == "training"][-1]
    [change] = training["changes"]
    assert (change["routineId"], change["before"], change["after"]) == (routine["id"], 100, 102.5)


def test_a_cut_cant_be_asked_for_while_a_training_change_adds_load(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = register_user(client)
    _, check_in = _training_check_in(client, headers)
    _ask(client, headers, check_in["id"], "Make barbell bench press heavier")  # now pending: 100 -> 102.5 kg
    before = _nutrition(_current(client, headers))

    reply = _ask(client, headers, check_in["id"], "Fewer calories please")

    assert reply["kind"] == "answer" and "Reject that training change first" in reply["text"]
    assert _nutrition(_current(client, headers)) == before


def test_the_reviewer_can_hold_a_revision_back(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedModel(
        chat={"intent": "adjust_nutrition", "reply": "On it.", "request": "Cut calories by 300 more"},
        nutrition={"action": "change", "new_calorie_target": 2050, "headline": "Cut", "evidence": ["Asked."]},
        reviewer={
            "findings": [{"severity": "warning", "message": "Too steep."}],
            "keep_nutrition": False,
            "keep_workout": True,
            "note": "A cut this size on top of last week's isn't supported by the trend.",
        },
    )
    _use(monkeypatch, model)
    check_in = _current(client, auth_headers)
    before = _nutrition(check_in)

    reply = _ask(client, auth_headers, check_in["id"], "Cut calories by 300 more")

    assert model.agents == ["chat", "nutrition", "reviewer"]
    assert reply["kind"] == "answer" and "isn't supported by the trend" in reply["text"]
    assert _nutrition(_current(client, auth_headers)) == before


def test_a_revision_stays_within_the_limits(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(
        monkeypatch,
        ScriptedModel(
            chat={"intent": "adjust_nutrition", "reply": "On it.", "request": "Eat 1,000 kcal more"},
            nutrition={
                "action": "change",
                "new_calorie_target": 3350,
                "headline": "More",
                "evidence": ["Asked."],
            },
            reviewer={"findings": [], "keep_nutrition": True, "keep_workout": True, "note": "Fine."},
        ),
    )
    check_in = _current(client, auth_headers)
    _ask(client, auth_headers, check_in["id"], "Eat 1,000 kcal more")

    assert _nutrition(_current(client, auth_headers))["changes"][0]["after"] == 2350 + 300, "the weekly limit"


def test_a_failed_revision_changes_and_stores_nothing(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(task: AgentTask[Any]) -> dict[str, Any]:
        raise ModelUnavailableError("down")

    _use(
        monkeypatch,
        ScriptedModel(
            chat={"intent": "adjust_nutrition", "reply": "On it.", "request": "More calories"}, nutrition=down
        ),
    )
    check_in = _current(client, auth_headers)
    before = _nutrition(check_in)

    response = client.post(
        f"{CHECK_INS}/{check_in['id']}/messages", headers=auth_headers, json={"text": "More calories"}
    )

    assert response.status_code == 503
    assert _nutrition(_current(client, auth_headers)) == before
    assert client.get(f"{CHECK_INS}/{check_in['id']}/messages", headers=auth_headers).json() == []


def test_the_message_kind_is_kept_in_the_conversation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    check_in = _current(client, auth_headers)
    _ask(client, auth_headers, check_in["id"], "Change my calories")
    _ask(client, auth_headers, check_in["id"], "More calories please")

    messages = client.get(f"{CHECK_INS}/{check_in['id']}/messages", headers=auth_headers).json()
    assert [(m["role"], m["kind"]) for m in messages] == [
        ("user", "answer"),
        ("coach", "clarification"),
        ("user", "answer"),
        ("coach", "revision"),
    ]


def test_an_empty_request_means_none_yet() -> None:
    from app.coach.agents.schemas import ChatReply

    reply = ChatReply.model_validate({"intent": "adjust_nutrition", "reply": "Up or down?", "request": " "})
    assert reply.request is None


def test_asking_to_keep_things_withdraws_the_pending_change(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from app.coach.service import WITHDRAWN

    check_in = _current(client, auth_headers)

    reply = _ask(client, auth_headers, check_in["id"], "Keep my calories the same")

    assert (reply["kind"], reply["text"]) == ("revision", WITHDRAWN[ProposalKind.NUTRITION])
    assert _nutrition(_current(client, auth_headers))["status"] == "rejected"


def test_changes_are_only_made_on_the_latest_check_in(client: TestClient) -> None:
    from app.coach.service import EARLIER_CHECK_IN
    from tests.test_coach_api import _start, _week_with_a_proposal

    headers = register_user(client)
    _week_with_a_proposal(client, headers)
    _start(client, headers, "first")
    first = _current(client, headers)
    for proposal in first["proposals"]:
        client.post(
            f"{CHECK_INS}/{first['id']}/proposals/{proposal['id']}/decision",
            headers=headers,
            json={"decision": "reject"},
        )
    assert _start(client, headers, "second").status_code == 201

    reply = _ask(client, headers, first["id"], "More calories please")

    assert (reply["kind"], reply["text"]) == ("answer", EARLIER_CHECK_IN)

    async def statuses() -> list[str]:
        from sqlalchemy import select

        from app.coach.models import Proposal
        from app.core.database import get_session_factory

        async with get_session_factory()() as session:
            rows = await session.scalars(select(Proposal.status).where(Proposal.check_in_id == first["id"]))
            return [status.value for status in rows]

    assert client.portal is not None
    assert client.portal.call(statuses) == ["rejected"] * len(first["proposals"]), "nothing added"


def test_a_proposal_decided_while_the_model_worked_is_left_as_decided(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.coach import service as service_module
    from app.coach.service import DECIDED_MEANWHILE

    check_in = _current(client, auth_headers)
    proposal = _nutrition(check_in)
    real = service_module.revise_proposal

    async def decided_meanwhile(*args: Any, **kwargs: Any) -> Any:
        revision = await real(*args, **kwargs)
        from sqlalchemy import update

        from app.coach.models import Proposal, ProposalStatus
        from app.core.database import get_session_factory

        async with get_session_factory()() as other:  # the user applying it on the card
            await other.execute(
                update(Proposal).where(Proposal.id == proposal["id"]).values(status=ProposalStatus.APPLIED)
            )
            await other.commit()
        return revision

    monkeypatch.setattr(service_module, "revise_proposal", decided_meanwhile)

    reply = _ask(client, auth_headers, check_in["id"], "Fewer calories please")

    assert (reply["kind"], reply["text"]) == ("answer", DECIDED_MEANWHILE)
    after = _nutrition(_current(client, auth_headers))
    assert (after["status"], after["headline"]) == ("applied", proposal["headline"])


def test_ordinary_words_arent_read_as_a_change() -> None:
    from app.coach.agents.model import _fake_chat

    context = {
        "question": "Did I have a great week?",
        "proposals": [],
        "week": {"summary": "A good week.", "routines": []},
    }
    assert _fake_chat(context)["intent"] == "explain"
