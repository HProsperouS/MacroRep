from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.helpers import plan_every_day
from tests.helpers import register_user as _new_user

CHECK_INS = "/api/v1/coach/check-ins"


def _log_food(client: TestClient, headers: dict[str, str], days_ago: int, calories: int = 2000) -> None:
    response = client.post(
        "/api/v1/food-log/entries",
        headers=headers,
        json={
            "date": (date.today() - timedelta(days=days_ago)).isoformat(),
            "meal": "lunch",
            "name": "Test meal",
            "amountLabel": "1 plate",
            "source": "quick-add",
            "calories": calories,
            "protein": 100,
            "carbs": 200,
            "fat": 60,
        },
    )
    assert response.status_code == 201


def _weigh_in(client: TestClient, headers: dict[str, str], days_ago: int, weight_kg: float) -> None:
    response = client.post(
        "/api/v1/body/weigh-ins",
        headers=headers,
        json={"date": (date.today() - timedelta(days=days_ago)).isoformat(), "weightKg": weight_kg},
    )
    assert response.status_code == 201


def _start(client: TestClient, headers: dict[str, str], key: str):
    return client.post(CHECK_INS, headers={**headers, "Idempotency-Key": key})


def _ready(client: TestClient, headers: dict[str, str]) -> dict:
    """The current check-in once generated. The test client runs the background
    generation before the POST returns, so it has always finished by now."""

    check_in = client.get(f"{CHECK_INS}/current", headers=headers).json()
    assert check_in["status"] not in ("running", "failed"), check_in
    return dict(check_in)


def test_current_check_in_seeded(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/coach/check-ins/current", headers=auth_headers)
    assert response.status_code == 200
    check_in = response.json()
    assert check_in is not None
    assert check_in["weekLabel"] == "Week 1"
    assert len(check_in["proposals"]) == 1


def test_decide_and_ask(client: TestClient, auth_headers: dict[str, str]) -> None:
    check_in = client.get("/api/v1/coach/check-ins/current", headers=auth_headers).json()
    proposal_id = check_in["proposals"][0]["id"]

    decision = client.post(
        f"/api/v1/coach/check-ins/{check_in['id']}/proposals/{proposal_id}/decision",
        headers=auth_headers,
        json={"decision": "apply"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "applied"

    reply = client.post(
        f"/api/v1/coach/check-ins/{check_in['id']}/messages",
        headers=auth_headers,
        json={"text": "Why this change?"},
    )
    assert reply.status_code == 200
    assert reply.json()["role"] == "coach"

    # Deciding an already-decided proposal again must be rejected, not silently overwritten.
    redecision = client.post(
        f"/api/v1/coach/check-ins/{check_in['id']}/proposals/{proposal_id}/decision",
        headers=auth_headers,
        json={"decision": "reject"},
    )
    assert redecision.status_code == 409


def test_start_check_in_requires_an_idempotency_key(client: TestClient) -> None:
    headers = _new_user(client)
    assert client.post(CHECK_INS, headers=headers).status_code == 422


def test_start_check_in_refuses_without_enough_data(client: TestClient) -> None:
    headers = _new_user(client)
    _log_food(client, headers, days_ago=0)
    _weigh_in(client, headers, days_ago=0, weight_kg=80)

    refused = _start(client, headers, "too-early")
    assert refused.status_code == 422
    assert "log food on at least 4" in refused.json()["detail"]
    assert "weigh in at least 2" in refused.json()["detail"]
    assert client.get(f"{CHECK_INS}/current", headers=headers).json() is None

    # A refusal doesn't consume the key: once the data exists, the same key succeeds.
    for days_ago in (1, 2, 3):
        _log_food(client, headers, days_ago=days_ago)
    _weigh_in(client, headers, days_ago=3, weight_kg=80.2)
    assert _start(client, headers, "too-early").status_code == 201


def test_replaying_an_idempotency_key_returns_the_same_check_in(client: TestClient) -> None:
    headers = _new_user(client)
    for days_ago in range(4):
        _log_food(client, headers, days_ago=days_ago)
    _weigh_in(client, headers, days_ago=5, weight_kg=80)
    _weigh_in(client, headers, days_ago=0, weight_kg=80)

    first = _start(client, headers, "week-1")
    assert first.status_code == 201
    assert first.json()["status"] == "running"  # generated in the background, after this answer
    check_in = _ready(client, headers)
    assert check_in["id"] == first.json()["id"]
    assert check_in["weekLabel"] == "Week 1"
    # 4/7 days logged is below the placeholder pipeline's adherence bar, so no proposals.
    assert check_in["proposals"] == []
    assert check_in["status"] == "reviewed"

    replay = _start(client, headers, "week-1")
    assert replay.status_code == 200
    assert replay.json() == check_in

    # A different key is a different request: nothing is pending, so a new check-in is made.
    second = _start(client, headers, "week-2")
    assert second.status_code == 201
    assert second.json()["id"] != check_in["id"]
    assert second.json()["weekLabel"] == "Week 2"


def test_idempotency_keys_are_scoped_per_user(client: TestClient) -> None:
    ids = []
    for _ in range(2):
        headers = _new_user(client)
        for days_ago in range(4):
            _log_food(client, headers, days_ago=days_ago)
        _weigh_in(client, headers, days_ago=4, weight_kg=70)
        _weigh_in(client, headers, days_ago=0, weight_kg=70)
        response = _start(client, headers, "shared-key")
        assert response.status_code == 201
        ids.append(response.json()["id"])
    assert ids[0] != ids[1]


def _check_in_with_a_proposal(client: TestClient, headers: dict[str, str]) -> dict:
    # Every day logged and the trend off a maintain goal: the placeholder proposes a calorie change.
    for days_ago in range(7):
        _log_food(client, headers, days_ago=days_ago)
    _weigh_in(client, headers, days_ago=6, weight_kg=80)
    _weigh_in(client, headers, days_ago=0, weight_kg=78)
    _start(client, headers, "with-proposal")
    check_in = _ready(client, headers)
    assert len(check_in["proposals"]) == 1
    return dict(check_in)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"decision": "maybe"}, 422),
        ({"decision": "apply", "changes": [{"id": "calories", "after": -1}]}, 422),
        ({"decision": "apply", "changes": [{"id": "not-in-proposal", "after": 2000}]}, 422),
        ({"decision": "apply", "changes": [{"id": "calories", "after": 0}]}, 422),
        ({"decision": "apply", "changes": [{"id": "calories", "after": 2100}]}, 200),
    ],
    ids=[
        "unknown decision",
        "negative value",
        "value not in the proposal",
        "below the allowed range",
        "in range",
    ],
)
def test_proposal_decisions_are_validated(client: TestClient, body: dict, expected: int) -> None:
    headers = _new_user(client)
    check_in = _check_in_with_a_proposal(client, headers)
    proposal_id = check_in["proposals"][0]["id"]
    response = client.post(
        f"{CHECK_INS}/{check_in['id']}/proposals/{proposal_id}/decision", headers=headers, json=body
    )
    assert response.status_code == expected, response.text


def _targets(client: TestClient, headers: dict[str, str]) -> dict:
    return dict(client.get("/api/v1/nutrition/targets", headers=headers).json())


def _decide(client: TestClient, headers: dict[str, str], check_in: dict, body: dict):
    proposal_id = check_in["proposals"][0]["id"]
    return client.post(
        f"{CHECK_INS}/{check_in['id']}/proposals/{proposal_id}/decision", headers=headers, json=body
    )


def test_applying_a_nutrition_proposal_updates_the_daily_calorie_target(client: TestClient) -> None:
    headers = _new_user(client)
    check_in = _check_in_with_a_proposal(client, headers)
    proposed = check_in["proposals"][0]["changes"][0]["after"]
    before = _targets(client, headers)

    assert _decide(client, headers, check_in, {"decision": "apply"}).status_code == 200

    after = _targets(client, headers)
    assert after["calories"] == round(proposed)
    assert {key: after[key] for key in ("protein", "carbs", "fat")} == {
        key: before[key] for key in ("protein", "carbs", "fat")
    }


def test_editing_a_nutrition_proposal_applies_the_edited_value(client: TestClient) -> None:
    headers = _new_user(client)
    check_in = _check_in_with_a_proposal(client, headers)

    response = _decide(
        client, headers, check_in, {"decision": "apply", "changes": [{"id": "calories", "after": 2050}]}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "edited"
    assert _targets(client, headers)["calories"] == 2050


def test_rejecting_a_nutrition_proposal_leaves_the_target_alone(client: TestClient) -> None:
    headers = _new_user(client)
    check_in = _check_in_with_a_proposal(client, headers)
    before = _targets(client, headers)

    assert _decide(client, headers, check_in, {"decision": "reject"}).status_code == 200

    assert _targets(client, headers) == before


@pytest.mark.parametrize("calories", [999, 6_001])
def test_an_out_of_range_target_is_refused_and_the_proposal_stays_pending(
    client: TestClient, calories: int
) -> None:
    headers = _new_user(client)
    check_in = _check_in_with_a_proposal(client, headers)
    before = _targets(client, headers)

    response = _decide(
        client, headers, check_in, {"decision": "apply", "changes": [{"id": "calories", "after": calories}]}
    )

    assert response.status_code == 422
    assert "1,000-6,000" in response.json()["detail"]
    assert _targets(client, headers) == before
    # Still pending, so the user can edit it into range instead of being stuck.
    assert (
        _decide(
            client, headers, check_in, {"decision": "apply", "changes": [{"id": "calories", "after": 2000}]}
        ).status_code
        == 200
    )


def test_a_target_far_below_the_macros_is_refused(client: TestClient) -> None:
    headers = _new_user(client)
    # These macros add up to 3,300 kcal; a target under half of that can't be right.
    assert (
        client.put(
            "/api/v1/nutrition/targets",
            headers=headers,
            json={"calories": 3300, "protein": 300, "carbs": 300, "fat": 100},
        ).status_code
        == 200
    )
    check_in = _check_in_with_a_proposal(client, headers)

    response = _decide(
        client, headers, check_in, {"decision": "apply", "changes": [{"id": "calories", "after": 1500}]}
    )

    assert response.status_code == 422
    assert "too low" in response.json()["detail"]


@pytest.mark.parametrize(("text", "expected"), [("x" * 500, 200), ("x" * 501, 422), ("   ", 422)])
def test_coach_messages_are_bounded(
    client: TestClient, auth_headers: dict[str, str], text: str, expected: int
) -> None:
    check_in = client.get(f"{CHECK_INS}/current", headers=auth_headers).json()
    response = client.post(
        f"{CHECK_INS}/{check_in['id']}/messages", headers=auth_headers, json={"text": text}
    )
    assert response.status_code == expected


def test_check_in_reports_the_week_against_target(client: TestClient) -> None:
    headers = _new_user(client)
    targets = client.put(
        "/api/v1/nutrition/targets",
        headers=headers,
        json={"calories": 2000, "protein": 150, "carbs": 200, "fat": 60},
    )
    assert targets.status_code == 200
    for days_ago in (0, 1, 3, 4, 5, 6):
        _log_food(client, headers, days_ago=days_ago)
    # A light day, logged under half the 2000 kcal target: still counted as eaten.
    light_day = client.post(
        "/api/v1/food-log/entries",
        headers=headers,
        json={
            "date": (date.today() - timedelta(days=2)).isoformat(),
            "meal": "lunch",
            "name": "Soup",
            "amountLabel": "1 bowl",
            "source": "quick-add",
            "calories": 600,
            "protein": 30,
            "carbs": 70,
            "fat": 20,
        },
    )
    assert light_day.status_code == 201
    _weigh_in(client, headers, days_ago=6, weight_kg=80)
    _weigh_in(client, headers, days_ago=0, weight_kg=80)

    _start(client, headers, "gap")
    check_in = _ready(client, headers)
    stats = {stat["label"]: stat["value"] for stat in check_in["stats"]}
    assert stats["Vs target"] == "-1,400 kcal"
    assert "1,400 kcal under target" in check_in["summary"]
    assert "1 of them fell under half the target" in check_in["summary"]


def _log_workout(client: TestClient, headers: dict[str, str], days_ago: int, rpe: float | None) -> None:
    started = datetime.combine(date.today() - timedelta(days=days_ago), time(12, 0), tzinfo=UTC)
    response = client.post(
        "/api/v1/workouts/sessions",
        headers=headers,
        json={
            "planId": None,
            "name": "Session",
            "startedAt": started.isoformat(),
            "finishedAt": (started + timedelta(hours=1)).isoformat(),
            "exercises": [
                {
                    "exerciseId": "exercise-bench-press",
                    "name": "Barbell Bench Press",
                    "sets": [{"kind": "working", "weightKg": 60, "reps": 8, "rpe": rpe}],
                }
            ],
        },
    )
    assert response.status_code == 201


def test_check_in_reports_completion_and_effort(client: TestClient) -> None:
    headers = _new_user(client)
    plan_every_day(client, headers)
    for days_ago in range(4):
        _log_food(client, headers, days_ago=days_ago)
    _weigh_in(client, headers, days_ago=6, weight_kg=80)
    _weigh_in(client, headers, days_ago=0, weight_kg=80)
    _log_workout(client, headers, days_ago=1, rpe=8)
    _log_workout(client, headers, days_ago=5, rpe=9)  # training began then, though the routine is new

    _start(client, headers, "effort")
    check_in = _ready(client, headers)
    stats = {stat["label"]: stat["value"] for stat in check_in["stats"]}
    # 5 finished plan days since training began; today isn't due until trained.
    assert stats["Workouts"] == "2/5 (40%)"
    assert stats["Avg RPE"] == "8.5"
    assert "Average effort was RPE 8.5." in check_in["summary"]


def test_check_in_without_rpe_or_a_plan(client: TestClient) -> None:
    headers = _new_user(client)
    for days_ago in range(4):
        _log_food(client, headers, days_ago=days_ago)
    _weigh_in(client, headers, days_ago=6, weight_kg=80)
    _weigh_in(client, headers, days_ago=0, weight_kg=80)
    _log_workout(client, headers, days_ago=1, rpe=None)

    _start(client, headers, "no-rpe")
    check_in = _ready(client, headers)
    stats = {stat["label"]: stat["value"] for stat in check_in["stats"]}
    assert stats["Workouts"] == "1/0"
    assert stats["Avg RPE"] == "—"
    assert "RPE" not in check_in["summary"]


def test_pending_proposals_block_a_new_check_in(client: TestClient) -> None:
    headers = _new_user(client)
    # Every day logged (100% adherence) and the trend dropping 0.2 kg against a
    # maintain goal: enough for the placeholder pipeline to propose a change.
    for days_ago in range(7):
        _log_food(client, headers, days_ago=days_ago)
    _weigh_in(client, headers, days_ago=6, weight_kg=80)
    _weigh_in(client, headers, days_ago=0, weight_kg=78)

    first = _start(client, headers, "with-proposal")
    assert first.status_code == 201
    check_in = _ready(client, headers)
    assert check_in["status"] == "needs-review"
    assert len(check_in["proposals"]) == 1

    blocked = _start(client, headers, "another-key")
    assert blocked.status_code == 409

    # Replaying the original key is still fine: it's a read, not a new check-in.
    assert _start(client, headers, "with-proposal").status_code == 200

    proposal_id = check_in["proposals"][0]["id"]
    decided = client.post(
        f"{CHECK_INS}/{check_in['id']}/proposals/{proposal_id}/decision",
        headers=headers,
        json={"decision": "reject"},
    )
    assert decided.status_code == 200
    assert _start(client, headers, "another-key").status_code == 201


def _week_with_a_proposal(client: TestClient, headers: dict[str, str]) -> None:
    for days_ago in range(7):
        _log_food(client, headers, days_ago=days_ago)
    _weigh_in(client, headers, days_ago=6, weight_kg=80)
    _weigh_in(client, headers, days_ago=0, weight_kg=78)


def _run_metrics(caplog: pytest.LogCaptureFixture, check_in_id: str) -> dict:
    """What the run logged when it ended."""

    [record] = [
        record
        for record in caplog.records
        if record.message == "check-in run finished" and getattr(record, "check_in_id", None) == check_in_id
    ]
    return record.run_metrics  # type: ignore[attr-defined,no-any-return]


def test_a_check_in_is_generated_in_the_background(client: TestClient) -> None:
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    started = _start(client, headers, "bg")
    assert started.status_code == 201
    assert started.json()["status"] == "running"
    assert started.json()["proposals"] == []
    assert [step["status"] for step in started.json()["pipeline"]] == ["done", "running"]

    ready = _ready(client, headers)
    assert ready["status"] == "needs-review"
    assert len(ready["proposals"]) == 1
    assert ready["failureReason"] is None


def test_a_run_records_how_it_went(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)
    with caplog.at_level("INFO", logger="app.coach.service"):
        check_in_id = _start(client, headers, "metrics").json()["id"]

    metrics = _run_metrics(caplog, check_in_id)
    assert (metrics["outcome"], metrics["error"], metrics["model"], metrics["resumed"]) == (
        "completed",
        None,
        "fake",
        False,
    )
    assert metrics["calls"] == 3 and metrics["duration_ms"] >= 0
    assert {name: agent["outcome"] for name, agent in metrics["agents"].items()} == {
        "nutrition": "valid",
        "workout": "valid",
        "reviewer": "valid",
    }


def test_a_failed_generation_is_reported_and_changes_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="app.coach.service")
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)
    targets_before = _targets(client, headers)

    async def broken(*_: object) -> None:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.coach.agents.model.FakeCoachModel.generate", broken)
    assert _start(client, headers, "fails").status_code == 201

    current = client.get(f"{CHECK_INS}/current", headers=headers).json()
    assert current["status"] == "failed"
    assert current["proposals"] == []
    assert "Nothing was changed" in current["failureReason"]
    assert "model unavailable" not in current["failureReason"], "internal errors stay in the logs"
    assert "failed" in [step["status"] for step in current["pipeline"]]
    metrics = _run_metrics(caplog, current["id"])
    assert (metrics["outcome"], metrics["error"]) == ("failed", "RuntimeError")
    assert metrics["agents"]["nutrition"]["errors"] == ["RuntimeError"]
    assert _targets(client, headers) == targets_before
    history = client.get("/api/v1/progress", headers=headers, params={"range": "1M"}).json()["checkIns"]
    assert history == [], "a failed check-in has no outcome to list"

    # A failed check-in doesn't block the next one.
    monkeypatch.undo()
    assert _start(client, headers, "retry").status_code == 201
    assert _ready(client, headers)["status"] == "needs-review"


def _backdate_check_in(client: TestClient, check_in_id: str, minutes: int) -> None:
    from sqlalchemy import update

    from app.coach.models import CheckIn as CheckInRow
    from app.core.database import get_session_factory

    async def move() -> None:
        async with get_session_factory()() as session:
            await session.execute(
                update(CheckInRow)
                .where(CheckInRow.id == check_in_id)
                .values(created_utc=datetime.now(UTC) - timedelta(minutes=minutes))
            )
            await session.commit()

    assert client.portal is not None
    client.portal.call(move)


def test_a_running_check_in_blocks_another_until_it_is_lost(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    async def never_runs(_: str) -> None:  # as if the server restarted before the run began
        return None

    monkeypatch.setattr("app.coach.router.generate_check_in", never_runs)
    check_in_id = _start(client, headers, "lost").json()["id"]

    blocked = _start(client, headers, "second")
    assert blocked.status_code == 409
    assert "still being prepared" in blocked.json()["detail"]

    _backdate_check_in(client, check_in_id, minutes=11)
    current = client.get(f"{CHECK_INS}/current", headers=headers).json()
    assert current["status"] == "failed"
    assert "interrupted" in current["failureReason"]

    monkeypatch.undo()
    assert _start(client, headers, "after-lost").status_code == 201


def test_running_the_generation_twice_does_not_duplicate_proposals(client: TestClient) -> None:
    from app.coach.runner import generate_check_in

    headers = _new_user(client)
    check_in = _check_in_with_a_proposal(client, headers)

    assert client.portal is not None
    client.portal.call(generate_check_in, check_in["id"])

    assert len(_ready(client, headers)["proposals"]) == 1


def test_an_edited_proposal_keeps_what_was_proposed_and_when_it_was_decided(client: TestClient) -> None:
    headers = _new_user(client)
    check_in = _check_in_with_a_proposal(client, headers)
    proposed = check_in["proposals"][0]["changes"][0]["after"]
    assert check_in["proposals"][0]["decidedAt"] is None

    decided = _decide(
        client, headers, check_in, {"decision": "apply", "changes": [{"id": "calories", "after": 2050}]}
    ).json()

    assert decided["changes"][0]["after"] == 2050
    assert decided["proposedChanges"][0]["after"] == proposed
    assert decided["decidedAt"] is not None
    assert decided["decidedAt"].endswith(("Z", "+00:00"))
    stored = _ready(client, headers)["proposals"][0]
    assert stored["proposedChanges"][0]["after"] == proposed


def test_a_run_that_outlived_the_stale_sweep_does_not_bring_its_check_in_back(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.coach.runner import generate_check_in

    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    async def never_runs(_: str) -> None:
        return None

    monkeypatch.setattr("app.coach.router.generate_check_in", never_runs)
    check_in_id = _start(client, headers, "slow").json()["id"]
    _backdate_check_in(client, check_in_id, minutes=11)
    assert client.get(f"{CHECK_INS}/current", headers=headers).json()["status"] == "failed"

    # The slow run finally finishes: it must not overwrite the failure with proposals.
    assert client.portal is not None
    client.portal.call(generate_check_in, check_in_id)

    current = client.get(f"{CHECK_INS}/current", headers=headers).json()
    assert current["status"] == "failed"
    assert current["proposals"] == []


def test_a_run_whose_check_in_moved_on_meanwhile_is_logged_as_discarded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.coach.repository import CoachRepository

    caplog.set_level("INFO", logger="app.coach.service")
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    async def already_moved_on(*_: object, **__: object) -> bool:
        return False  # as when the stale sweep failed it, or another run finished it, mid-run

    monkeypatch.setattr(CoachRepository, "finish_run", already_moved_on)
    check_in_id = _start(client, headers, "moved-on").json()["id"]

    metrics = _run_metrics(caplog, check_in_id)
    assert (metrics["outcome"], metrics["calls"]) == ("discarded", 3)


def test_a_model_that_cant_be_set_up_fails_the_check_in(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="app.coach.service")
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    def broken() -> None:
        raise RuntimeError("bad model settings")

    monkeypatch.setattr("app.coach.service.get_coach_model", broken)
    check_in_id = _start(client, headers, "no-model").json()["id"]

    assert client.get(f"{CHECK_INS}/current", headers=headers).json()["status"] == "failed"
    metrics = _run_metrics(caplog, check_in_id)
    assert (metrics["outcome"], metrics["error"], metrics["model"], metrics["calls"]) == (
        "failed",
        "RuntimeError",
        "unknown",
        0,
    )


def test_a_run_that_takes_too_long_is_stopped_and_marked_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="app.coach.service")
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)
    monkeypatch.setattr("app.coach.service.RUN_TIMEOUT_SECONDS", 0.2)

    async def slow(*_: object) -> None:
        await asyncio.sleep(1)

    monkeypatch.setattr("app.coach.agents.model.FakeCoachModel.generate", slow)

    _start(client, headers, "too-slow")

    current = client.get(f"{CHECK_INS}/current", headers=headers).json()
    assert current["status"] == "failed"
    metrics = _run_metrics(caplog, current["id"])
    assert (metrics["outcome"], metrics["error"]) == ("timed_out", "TimeoutError")
    assert {agent["errors"][0] for agent in metrics["agents"].values()} == {"CancelledError"}


def test_an_error_while_saving_the_proposals_marks_the_check_in_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    async def broken(*_: object) -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr("app.coach.repository.CoachRepository.add_proposals", broken)
    _start(client, headers, "save-fails")

    current = client.get(f"{CHECK_INS}/current", headers=headers).json()
    assert current["status"] == "failed", "never left stuck as running"
    assert current["proposals"] == []


def test_a_retry_after_a_failure_keeps_the_week_number(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    async def broken(*_: object) -> None:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.coach.agents.model.FakeCoachModel.generate", broken)
    assert _start(client, headers, "fails").json()["weekLabel"] == "Week 1"
    monkeypatch.undo()
    assert _start(client, headers, "retry").json()["weekLabel"] == "Week 1"


def test_replaying_the_key_of_a_lost_run_reports_it_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    async def never_runs(_: str) -> None:
        return None

    monkeypatch.setattr("app.coach.router.generate_check_in", never_runs)
    check_in_id = _start(client, headers, "lost").json()["id"]
    _backdate_check_in(client, check_in_id, minutes=11)

    replay = _start(client, headers, "lost")
    assert replay.status_code == 200
    assert replay.json()["status"] == "failed"


def test_a_refused_apply_records_no_decision_time(client: TestClient) -> None:
    headers = _new_user(client)
    check_in = _check_in_with_a_proposal(client, headers)

    refused = _decide(
        client, headers, check_in, {"decision": "apply", "changes": [{"id": "calories", "after": 999}]}
    )
    assert refused.status_code == 422

    proposal = _ready(client, headers)["proposals"][0]
    assert proposal["status"] == "pending"
    assert proposal["decidedAt"] is None


def _log_bench(
    client: TestClient, headers: dict[str, str], days_ago: int, weight_kg: float, rpe: float
) -> None:
    started = datetime.combine(date.today() - timedelta(days=days_ago), time(12, 0), tzinfo=UTC)
    sets = [{"kind": "working", "weightKg": weight_kg, "reps": 5, "rpe": rpe}] * 3
    response = client.post(
        "/api/v1/workouts/sessions",
        headers=headers,
        json={
            "planId": None,
            "name": "Push",
            "startedAt": started.isoformat(),
            "finishedAt": (started + timedelta(hours=1)).isoformat(),
            "exercises": [
                {"exerciseId": "exercise-bench-press", "name": "Barbell Bench Press", "sets": sets}
            ],
        },
    )
    assert response.status_code == 201


def test_logged_training_leads_to_a_training_proposal_for_the_scheduled_routine(client: TestClient) -> None:
    headers = _new_user(client)
    routine = client.post(
        "/api/v1/workouts/routines",
        headers=headers,
        json={
            "name": "Push",
            "weekLabel": "Week 1",
            "estimatedMinutes": 45,
            "exercises": [
                {
                    "exerciseId": "exercise-bench-press",
                    "restSeconds": 120,
                    "sets": [{"kind": "working", "targetWeightKg": 100, "targetReps": 5}] * 3,
                }
            ],
        },
    ).json()
    for day in range(7):
        client.put(f"/api/v1/workouts/plan/{day}", headers=headers, json={"routineId": routine["id"]})
    _week_with_a_proposal(client, headers)
    # Strength has slipped while effort climbed to RPE 9.5: time to ease off.
    _log_bench(client, headers, days_ago=14, weight_kg=100, rpe=8)
    _log_bench(client, headers, days_ago=2, weight_kg=95, rpe=9.5)
    _log_bench(client, headers, days_ago=1, weight_kg=95, rpe=9.5)

    _start(client, headers, "training")
    check_in = _ready(client, headers)

    training = next(p for p in check_in["proposals"] if p["kind"] == "training")
    change = training["changes"][0]
    assert change["label"] == "Barbell Bench Press · target weight"
    assert (change["before"], change["after"], change["unit"]) == (100.0, 95.0, "kg")
    assert (change["routineId"], change["exerciseId"], change["field"]) == (
        routine["id"],
        "exercise-bench-press",
        "target_weight_kg",
    )
    assert any("RPE 9.5" in line for line in training["evidence"])
    assert [step["id"] for step in check_in["pipeline"]] == [
        "gather",
        "nutrition",
        "workout",
        "reviewer",
        "decide",
    ]


def test_a_finished_run_leaves_no_checkpoints_behind(client: TestClient) -> None:
    from app.coach.agents.checkpoint import get_checkpointer

    headers = _new_user(client)
    check_in = _check_in_with_a_proposal(client, headers)

    async def saved() -> object:
        return await get_checkpointer().aget_tuple({"configurable": {"thread_id": check_in["id"]}})

    assert client.portal is not None
    assert client.portal.call(saved) is None


def test_a_run_resumed_long_after_it_began_is_failed_not_finished(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.coach.runner import generate_check_in

    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    async def never_runs(_: str) -> None:
        return None

    monkeypatch.setattr("app.coach.router.generate_check_in", never_runs)
    check_in_id = _start(client, headers, "old").json()["id"]
    _backdate_check_in(client, check_in_id, minutes=60)

    assert client.portal is not None
    client.portal.call(generate_check_in, check_in_id)  # as the startup resume would

    row = _check_in_row(client, check_in_id)
    assert row.status.value == "failed"  # type: ignore[attr-defined]
    assert "interrupted" in (row.failure_reason or "")  # type: ignore[attr-defined]


def _check_in_row(client: TestClient, check_in_id: str) -> object:
    from app.coach.models import CheckIn as CheckInRow
    from app.core.database import get_session_factory

    async def load() -> object:
        async with get_session_factory()() as session:
            return await session.get(CheckInRow, check_in_id)

    assert client.portal is not None
    return client.portal.call(load)


def test_a_run_stopped_at_shutdown_stays_running_to_be_resumed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.coach.runner import generate_check_in, stop_running_check_ins

    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    async def never_runs(_: str) -> None:
        return None

    monkeypatch.setattr("app.coach.router.generate_check_in", never_runs)
    check_in_id = _start(client, headers, "shutdown").json()["id"]

    started = asyncio.Event()

    async def slow(*_: object) -> None:
        started.set()
        await asyncio.sleep(30)

    monkeypatch.setattr("app.coach.agents.model.FakeCoachModel.generate", slow)

    async def run_then_shut_down() -> bool:
        task = asyncio.create_task(generate_check_in(check_in_id))
        await started.wait()
        await stop_running_check_ins()
        return task.cancelled()

    assert client.portal is not None
    assert client.portal.call(run_then_shut_down) is True
    assert _check_in_row(client, check_in_id).status.value == "running"  # type: ignore[attr-defined]


def test_the_snapshot_counts_working_sets_only(client: TestClient) -> None:
    from zoneinfo import ZoneInfo

    from app.core.database import get_session_factory
    from app.progress.repository import ProgressRepository

    headers = _new_user(client)
    routine = client.post(
        "/api/v1/workouts/routines",
        headers=headers,
        json={
            "name": "Push",
            "weekLabel": "Week 1",
            "estimatedMinutes": 45,
            "exercises": [
                {
                    "exerciseId": "exercise-bench-press",
                    "restSeconds": 120,
                    "sets": [
                        {"kind": "warmup", "targetWeightKg": 40, "targetReps": 10},
                        *[{"kind": "working", "targetWeightKg": 80, "targetReps": 5}] * 3,
                        {"kind": "drop", "targetWeightKg": 120, "targetReps": 3},
                    ],
                }
            ],
        },
    ).json()
    client.put("/api/v1/workouts/plan/0", headers=headers, json={"routineId": routine["id"]})
    started = datetime.combine(date.today() - timedelta(days=1), time(12, 0), tzinfo=UTC)
    client.post(
        "/api/v1/workouts/sessions",
        headers=headers,
        json={
            "planId": None,
            "name": "Push",
            "startedAt": started.isoformat(),
            "finishedAt": (started + timedelta(hours=1)).isoformat(),
            "exercises": [
                {
                    "exerciseId": "exercise-bench-press",
                    "name": "Barbell Bench Press",
                    "sets": [
                        {"kind": "working", "weightKg": 80, "reps": 5, "rpe": 7},
                        {"kind": "failure", "weightKg": 80, "reps": 7, "rpe": 10},
                    ],
                }
            ],
        },
    )
    owner_id = client.get("/api/v1/users/me", headers=headers).json()["id"]

    async def read() -> tuple[object, object]:
        async with get_session_factory()() as session:
            repository = ProgressRepository(session)
            today = date.today()
            return (
                await repository.scheduled_routines(owner_id),
                await repository.exercise_trends(
                    owner_id, ["exercise-bench-press"], today - timedelta(days=6), today, ZoneInfo("UTC")
                ),
            )

    assert client.portal is not None
    routines, trends = client.portal.call(read)
    exercise = routines[0]["exercises"][0]  # type: ignore[index]
    assert (exercise["working_sets"], exercise["target_weight_kg"]) == (3, 80.0), "no warm-up or drop set"
    assert trends["exercise-bench-press"]["recent_avg_rpe"] == 7.0, "the failure set's RPE 10 is left out"  # type: ignore[index]


# --- Applying training proposals ----------------------------------------------


def _routine_sets(client: TestClient, headers: dict[str, str], routine_id: str) -> list[dict]:
    routine = next(
        r for r in client.get("/api/v1/workouts/routines", headers=headers).json() if r["id"] == routine_id
    )
    return [
        {"kind": s["kind"], "w": s["targetWeightKg"], "r": s["targetReps"]}
        for s in routine["exercises"][0]["sets"]
    ]


def _training_check_in(client: TestClient, headers: dict[str, str]) -> tuple[dict, dict]:
    """A routine (warm-up + 3 x 100 kg x 5 bench) and a check-in proposing to ease it to 95 kg."""

    routine = client.post(
        "/api/v1/workouts/routines",
        headers=headers,
        json={
            "name": "Push",
            "weekLabel": "Week 1",
            "estimatedMinutes": 45,
            "exercises": [
                {
                    "exerciseId": "exercise-bench-press",
                    "restSeconds": 120,
                    "sets": [
                        {"kind": "warmup", "targetWeightKg": 40, "targetReps": 10},
                        *[{"kind": "working", "targetWeightKg": 100, "targetReps": 5}] * 3,
                    ],
                }
            ],
        },
    ).json()
    for day in range(7):
        client.put(f"/api/v1/workouts/plan/{day}", headers=headers, json={"routineId": routine["id"]})
    _week_with_a_proposal(client, headers)
    _log_bench(client, headers, days_ago=14, weight_kg=100, rpe=8)
    _log_bench(client, headers, days_ago=2, weight_kg=95, rpe=9.5)
    _log_bench(client, headers, days_ago=1, weight_kg=95, rpe=9.5)
    _start(client, headers, "training")
    check_in = _ready(client, headers)
    training = next(p for p in check_in["proposals"] if p["kind"] == "training")
    return routine, {**check_in, "proposals": [training]}


def test_applying_a_training_proposal_updates_the_routine(client: TestClient) -> None:
    headers = _new_user(client)
    routine, check_in = _training_check_in(client, headers)

    decided = _decide(client, headers, check_in, {"decision": "apply"})

    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "applied"
    assert _routine_sets(client, headers, routine["id"]) == [
        {"kind": "warmup", "w": 40.0, "r": 10},
        *[{"kind": "working", "w": 95.0, "r": 5}] * 3,
    ]
    # Today's planned workout, which pre-fills the logger, follows the routine.
    today = client.get("/api/v1/workouts/today", headers=headers).json()
    assert [s["targetWeightKg"] for s in today["exercises"][0]["sets"]] == [40.0, 95.0, 95.0, 95.0]


def test_an_edited_training_value_within_the_limits_is_applied(client: TestClient) -> None:
    headers = _new_user(client)
    routine, check_in = _training_check_in(client, headers)
    change_id = check_in["proposals"][0]["changes"][0]["id"]

    decided = _decide(
        client, headers, check_in, {"decision": "apply", "changes": [{"id": change_id, "after": 92.5}]}
    )

    assert decided.json()["status"] == "edited"
    assert decided.json()["proposedChanges"][0]["after"] == 95.0
    assert [s["w"] for s in _routine_sets(client, headers, routine["id"])][1:] == [92.5] * 3


def test_an_edited_training_value_past_the_limits_is_refused(client: TestClient) -> None:
    headers = _new_user(client)
    routine, check_in = _training_check_in(client, headers)
    change_id = check_in["proposals"][0]["changes"][0]["id"]
    before = _routine_sets(client, headers, routine["id"])

    refused = _decide(
        client, headers, check_in, {"decision": "apply", "changes": [{"id": change_id, "after": 85}]}
    )

    assert refused.status_code == 422
    assert "at most 10%" in refused.json()["detail"]
    assert _routine_sets(client, headers, routine["id"]) == before
    assert _ready(client, headers)["proposals"][0]["status"] == "pending"


def test_a_training_proposal_is_refused_once_the_routine_changed(client: TestClient) -> None:
    headers = _new_user(client)
    routine, check_in = _training_check_in(client, headers)
    edited = {
        "name": "Push",
        "weekLabel": "Week 1",
        "estimatedMinutes": 45,
        "exercises": [
            {
                "exerciseId": "exercise-bench-press",
                "restSeconds": 120,
                "sets": [{"kind": "working", "targetWeightKg": 105, "targetReps": 5}] * 3,
            }
        ],
    }
    client.put(f"/api/v1/workouts/routines/{routine['id']}", headers=headers, json=edited)

    refused = _decide(client, headers, check_in, {"decision": "apply"})

    assert refused.status_code == 409
    assert "out of date" in refused.json()["detail"]
    assert [s["w"] for s in _routine_sets(client, headers, routine["id"])] == [105.0] * 3


def test_a_training_proposal_for_a_deleted_routine_is_refused(client: TestClient) -> None:
    headers = _new_user(client)
    routine, check_in = _training_check_in(client, headers)
    client.delete(f"/api/v1/workouts/routines/{routine['id']}", headers=headers)

    refused = _decide(client, headers, check_in, {"decision": "apply"})

    assert refused.status_code == 409
    assert _decide(client, headers, check_in, {"decision": "reject"}).status_code == 200


def test_rejecting_a_training_proposal_leaves_the_routine_alone(client: TestClient) -> None:
    headers = _new_user(client)
    routine, check_in = _training_check_in(client, headers)
    before = _routine_sets(client, headers, routine["id"])

    assert _decide(client, headers, check_in, {"decision": "reject"}).status_code == 200
    assert _routine_sets(client, headers, routine["id"]) == before


def _rewrite_proposal_changes(client: TestClient, proposal_id: str, changes: list[dict]) -> None:
    """Swap in other proposed changes, to exercise fields the fake agent never proposes."""

    from sqlalchemy import update

    from app.coach.models import Proposal as ProposalRow
    from app.core.database import get_session_factory

    async def write() -> None:
        async with get_session_factory()() as session:
            await session.execute(
                update(ProposalRow)
                .where(ProposalRow.id == proposal_id)
                .values(changes=changes, proposed_changes=changes)
            )
            await session.commit()

    assert client.portal is not None
    client.portal.call(write)


def _training_change(change_id: str, routine_id: str, field: str, before: float, after: float) -> dict:
    return {
        "id": change_id,
        "label": f"Bench · {field}",
        "unit": "sets" if field == "working_sets" else "reps",
        "before": before,
        "after": after,
        "step": 1,
        "routine_id": routine_id,
        "exercise_id": "exercise-bench-press",
        "field": field,
    }


def test_set_and_rep_changes_build_on_each_other(client: TestClient) -> None:
    headers = _new_user(client)
    routine, check_in = _training_check_in(client, headers)
    _rewrite_proposal_changes(
        client,
        check_in["proposals"][0]["id"],
        [
            _training_change("training-1", routine["id"], "working_sets", 3, 4),
            _training_change("training-2", routine["id"], "target_reps", 5, 6),
        ],
    )

    assert _decide(client, headers, check_in, {"decision": "apply"}).status_code == 200
    assert _routine_sets(client, headers, routine["id"]) == [
        {"kind": "warmup", "w": 40.0, "r": 10},
        *[{"kind": "working", "w": 100.0, "r": 6}] * 4,
    ]


def test_one_change_out_of_limits_means_none_are_applied(client: TestClient) -> None:
    headers = _new_user(client)
    routine, check_in = _training_check_in(client, headers)
    before = _routine_sets(client, headers, routine["id"])
    _rewrite_proposal_changes(
        client,
        check_in["proposals"][0]["id"],
        [
            _training_change("training-1", routine["id"], "working_sets", 3, 4),
            _training_change("training-2", routine["id"], "target_reps", 5, 9),  # +4 reps: too much
        ],
    )

    refused = _decide(client, headers, check_in, {"decision": "apply"})

    assert refused.status_code == 422
    assert "at most 3" in refused.json()["detail"]
    assert _routine_sets(client, headers, routine["id"]) == before


def test_a_change_without_a_routine_reference_is_refused(client: TestClient) -> None:
    headers = _new_user(client)
    routine, check_in = _training_check_in(client, headers)
    broken = {**_training_change("training-1", routine["id"], "target_reps", 5, 6), "routine_id": None}
    _rewrite_proposal_changes(client, check_in["proposals"][0]["id"], [broken])

    assert _decide(client, headers, check_in, {"decision": "apply"}).status_code == 422


def test_a_routine_saved_again_after_the_check_in_is_out_of_date_even_with_the_same_top_weight(
    client: TestClient,
) -> None:
    headers = _new_user(client)
    routine, check_in = _training_check_in(client, headers)
    # Still 100 kg at the top, but now 5 x 3: not the routine the proposal was made for.
    resaved = {
        "name": "Push",
        "weekLabel": "Week 1",
        "estimatedMinutes": 45,
        "exercises": [
            {
                "exerciseId": "exercise-bench-press",
                "restSeconds": 120,
                "sets": [{"kind": "working", "targetWeightKg": 100, "targetReps": 3}] * 5,
            }
        ],
    }
    client.put(f"/api/v1/workouts/routines/{routine['id']}", headers=headers, json=resaved)

    refused = _decide(client, headers, check_in, {"decision": "apply"})

    assert refused.status_code == 409
    assert [s["w"] for s in _routine_sets(client, headers, routine["id"])] == [100.0] * 5


def test_dropping_a_set_and_lowering_the_weight_together_check_against_the_original_routine(
    client: TestClient,
) -> None:
    headers = _new_user(client)
    routine, check_in = _training_check_in(client, headers)
    _rewrite_proposal_changes(
        client,
        check_in["proposals"][0]["id"],
        [
            _training_change("training-1", routine["id"], "working_sets", 3, 2),
            {**_training_change("training-2", routine["id"], "target_weight_kg", 100, 95), "unit": "kg"},
        ],
    )

    decided = _decide(client, headers, check_in, {"decision": "apply"})

    assert decided.status_code == 200, decided.text
    assert _routine_sets(client, headers, routine["id"]) == [
        {"kind": "warmup", "w": 40.0, "r": 10},
        *[{"kind": "working", "w": 95.0, "r": 5}] * 2,
    ]


def _leave_running(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch, key: str
) -> str:
    """Start a check-in whose background run never happens, as if its task died at once."""

    async def never_runs(_: str) -> None:
        return None

    _week_with_a_proposal(client, headers)
    monkeypatch.setattr("app.coach.router.generate_check_in", never_runs)
    check_in_id = str(_start(client, headers, key).json()["id"])
    monkeypatch.undo()
    return check_in_id


def test_a_run_failed_as_stale_leaves_no_checkpoints(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.coach.agents.checkpoint import get_checkpointer
    from app.coach.agents.graph import run_agents
    from app.coach.agents.model import FakeCoachModel
    from app.coach.models import CheckIn as CheckInRow
    from app.core.database import get_session_factory

    headers = _new_user(client)
    check_in_id = _leave_running(client, headers, monkeypatch, "stale-checkpoints")

    async def crash(*_: object) -> None:
        raise RuntimeError("worker died mid-run")

    async def half_run() -> object:
        async with get_session_factory()() as session:
            snapshot = (await session.get(CheckInRow, check_in_id)).input_snapshot  # type: ignore[union-attr]
        monkeypatch.setattr(FakeCoachModel, "generate", crash)
        try:
            await run_agents(
                snapshot, FakeCoachModel(), thread_id=check_in_id, checkpointer=get_checkpointer()
            )
        except RuntimeError:
            pass
        monkeypatch.undo()
        return await get_checkpointer().aget_tuple({"configurable": {"thread_id": check_in_id}})

    async def saved() -> object:
        return await get_checkpointer().aget_tuple({"configurable": {"thread_id": check_in_id}})

    assert client.portal is not None
    assert client.portal.call(half_run) is not None, "the interrupted run left checkpoints"

    _backdate_check_in(client, check_in_id, minutes=11)
    assert client.get(f"{CHECK_INS}/current", headers=headers).json()["status"] == "failed"
    assert client.portal.call(saved) is None


def test_startup_takes_over_only_runs_whose_owner_must_be_gone(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.coach.runner import resume_interrupted_check_ins, stop_running_check_ins

    young_user, old_user = _new_user(client), _new_user(client)
    young = _leave_running(client, young_user, monkeypatch, "young")
    old = _leave_running(client, old_user, monkeypatch, "old")
    # Past the run time limit: a live owner would have finished or failed it by now.
    _backdate_check_in(client, old, minutes=3)

    async def resume_and_settle() -> None:
        await resume_interrupted_check_ins()
        await asyncio.sleep(0.5)  # the old one runs at once; the young one is still waiting

    assert client.portal is not None
    client.portal.call(resume_and_settle)

    assert _check_in_row(client, old).status.value == "needs-review"  # type: ignore[attr-defined]
    assert _check_in_row(client, young).status.value == "running", "its owner may still be working on it"  # type: ignore[attr-defined]
    client.portal.call(stop_running_check_ins)


def _start_and_reject(client: TestClient, headers: dict[str, str], key: str):
    """Start a check-in and reject what it proposes, so the next one may start."""

    response = _start(client, headers, key)
    if response.status_code == 201:
        check_in = _ready(client, headers)
        for proposal in check_in["proposals"]:
            client.post(
                f"{CHECK_INS}/{check_in['id']}/proposals/{proposal['id']}/decision",
                headers=headers,
                json={"decision": "reject"},
            )
    return response


def test_check_ins_per_user_are_limited(client: TestClient) -> None:
    from app.shared.rate_limit import CHECK_INS_PER_USER

    headers = _new_user(client)
    assert _start(client, headers, "too-early").status_code == 422  # not counted: no model call
    _week_with_a_proposal(client, headers)
    for index in range(CHECK_INS_PER_USER.attempts):
        assert _start_and_reject(client, headers, f"k{index}").status_code == 201
    assert _start(client, headers, "k0").status_code == 200, "a replay is a read, still allowed"

    refused = _start(client, headers, "one-more")

    assert refused.status_code == 429
    assert refused.json()["detail"] == "That's a lot of check-ins for today. Try again in 24 hours."
    assert refused.headers["Retry-After"]
    other_user = _new_user(client)
    _week_with_a_proposal(client, other_user)
    assert _start(client, other_user, "k0").status_code == 201


def test_a_failed_check_in_doesnt_use_one_up(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.shared.rate_limit import CHECK_INS_PER_USER, user_limiter

    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    async def broken(*_: object) -> None:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.coach.agents.model.FakeCoachModel.generate", broken)
    for index in range(CHECK_INS_PER_USER.attempts + 1):
        assert _start(client, headers, f"fails-{index}").status_code == 201
        assert client.get(f"{CHECK_INS}/current", headers=headers).json()["status"] == "failed"

    assert all(not hits for key, hits in user_limiter._hits.items() if key[0] == "check_in")  # noqa: SLF001


def test_a_check_in_that_couldnt_be_saved_doesnt_use_one_up(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.shared.rate_limit import user_limiter

    headers = _new_user(client)
    _week_with_a_proposal(client, headers)

    async def broken(*_: object) -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr("app.coach.repository.CoachRepository.add_check_in", broken)
    with pytest.raises(RuntimeError):
        _start(client, headers, "not-saved")

    assert all(not hits for key, hits in user_limiter._hits.items() if key[0] == "check_in")  # noqa: SLF001


def test_switched_off_check_ins_are_not_limited(client: TestClient) -> None:
    from app.core.config import get_settings
    from app.main import app
    from app.shared.rate_limit import CHECK_INS_PER_USER, user_limiter

    headers = _new_user(client)
    _week_with_a_proposal(client, headers)
    settings = get_settings().model_copy(update={"rate_limits_enabled": False})
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        for index in range(CHECK_INS_PER_USER.attempts + 1):
            assert _start_and_reject(client, headers, f"k{index}").status_code == 201
    finally:
        app.dependency_overrides.pop(get_settings)
    assert user_limiter._hits == {}  # noqa: SLF001


def test_the_snapshot_records_the_users_training_experience(client: TestClient) -> None:
    from tests.test_onboarding import GUIDE, ONBOARDING

    headers = _new_user(client)
    assert (
        client.post(ONBOARDING, headers=headers, json={**GUIDE, "experienceLevel": "advanced"}).status_code
        == 200
    )
    _week_with_a_proposal(client, headers)

    check_in_id = _start(client, headers, "experience").json()["id"]

    assert _check_in_row(client, check_in_id).input_snapshot["experience_level"] == "advanced"  # type: ignore[attr-defined]


def test_a_plan_made_mid_week_isnt_read_as_missed_sessions(client: TestClient) -> None:
    # The workout agent holds progress back when completion looks low.
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)
    plan_every_day(client, headers)  # made today, with nothing logged before it

    check_in_id = _start(client, headers, "mid-week").json()["id"]

    snapshot = _check_in_row(client, check_in_id).input_snapshot  # type: ignore[attr-defined]
    assert (snapshot["workouts_planned"], snapshot["completion_percent"]) == (0, None)
    assert snapshot["adherence_percent"] == 100.0, "logged every day since the first"
