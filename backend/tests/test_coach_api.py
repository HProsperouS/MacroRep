from __future__ import annotations

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


@pytest.mark.parametrize(("text", "expected"), [("x" * 2_000, 200), ("x" * 2_001, 422), ("   ", 422)])
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
    _log_workout(client, headers, days_ago=2, rpe=9)

    _start(client, headers, "effort")
    check_in = _ready(client, headers)
    stats = {stat["label"]: stat["value"] for stat in check_in["stats"]}
    # 6 finished plan days in the 7-day window; today isn't due until trained.
    assert stats["Workouts"] == "2/6 (33%)"
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


def test_a_failed_generation_is_reported_and_changes_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _new_user(client)
    _week_with_a_proposal(client, headers)
    targets_before = _targets(client, headers)

    def broken(**_: object) -> None:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.coach.pipeline.draft_check_in", broken)
    assert _start(client, headers, "fails").status_code == 201

    current = client.get(f"{CHECK_INS}/current", headers=headers).json()
    assert current["status"] == "failed"
    assert current["proposals"] == []
    assert "Nothing was changed" in current["failureReason"]
    assert "model unavailable" not in current["failureReason"], "internal errors stay in the logs"
    assert "failed" in [step["status"] for step in current["pipeline"]]
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


def test_a_run_that_takes_too_long_is_stopped_and_marked_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    headers = _new_user(client)
    _week_with_a_proposal(client, headers)
    monkeypatch.setattr("app.coach.service.RUN_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr("app.coach.pipeline.draft_check_in", lambda **_: time.sleep(1))

    _start(client, headers, "too-slow")

    current = client.get(f"{CHECK_INS}/current", headers=headers).json()
    assert current["status"] == "failed"


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

    def broken(**_: object) -> None:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.coach.pipeline.draft_check_in", broken)
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
