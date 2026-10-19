from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.helpers import register_user


def test_today_plan_seeded(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/workouts/today", headers=auth_headers)
    assert response.status_code == 200
    plan = response.json()
    assert plan is not None
    assert plan["name"] == "Push day"
    assert len(plan["exercises"]) == 1
    assert plan["exercises"][0]["sets"][0]["kind"] == "warmup"


def test_search_and_create_exercise(client: TestClient, auth_headers: dict[str, str]) -> None:
    seeded = client.get("/api/v1/exercises", headers=auth_headers, params={"q": "bench"})
    assert seeded.status_code == 200
    assert any(exercise["name"] == "Barbell Bench Press" for exercise in seeded.json())

    created = client.post(
        "/api/v1/exercises",
        headers=auth_headers,
        json={"name": "Cable Fly", "equipment": "cable", "muscles": ["chest"]},
    )
    assert created.status_code == 201
    assert created.json()["source"] == "custom"


def test_search_exercises_rejects_invalid_equipment(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/exercises", headers=auth_headers, params={"equipment": "trampoline"})
    assert response.status_code == 422


def test_create_exercise_rejects_invalid_equipment(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/exercises",
        headers=auth_headers,
        json={"name": "Mystery Machine", "equipment": "trampoline", "muscles": ["chest"]},
    )
    assert response.status_code == 422


def test_finish_session_reports_pr(client: TestClient, auth_headers: dict[str, str]) -> None:
    started = datetime.now(UTC) - timedelta(minutes=45)
    finished = datetime.now(UTC)
    payload = {
        "planId": None,
        "name": "Freestyle push",
        "startedAt": started.isoformat(),
        "finishedAt": finished.isoformat(),
        "exercises": [
            {
                "exerciseId": "exercise-bench-press",
                "name": "Barbell Bench Press",
                "sets": [
                    {"kind": "working", "weightKg": 70, "reps": 8},
                    {"kind": "working", "weightKg": 70, "reps": 8},
                ],
            }
        ],
    }
    response = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["setsCompleted"] == 2
    assert body["volumeKg"] == 1120.0
    assert body["personalRecords"]


def _session_payload(exercise_id: str, sets: list[dict[str, object]], *, plan_id: str | None = None) -> dict:
    started = datetime.now(UTC) - timedelta(minutes=45)
    finished = datetime.now(UTC)
    return {
        "planId": plan_id,
        "name": "Session",
        "startedAt": started.isoformat(),
        "finishedAt": finished.isoformat(),
        "exercises": [{"exerciseId": exercise_id, "name": "Barbell Bench Press", "sets": sets}],
    }


def test_finish_session_rejects_unknown_exercise(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = _session_payload("does-not-exist", [{"kind": "working", "weightKg": 60, "reps": 5}])
    response = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=payload)
    assert response.status_code == 404


def test_finish_session_rejects_unknown_plan(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = _session_payload(
        "exercise-bench-press", [{"kind": "working", "weightKg": 60, "reps": 5}], plan_id="does-not-exist"
    )
    response = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=payload)
    assert response.status_code == 404


def test_finish_session_rejects_negative_reps(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = _session_payload("exercise-bench-press", [{"kind": "working", "weightKg": 60, "reps": -5}])
    response = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=payload)
    assert response.status_code == 422


def test_pr_baseline_excludes_warmup_sets(client: TestClient, auth_headers: dict[str, str]) -> None:
    # A very heavy warmup should not raise the bar for what counts as a working-set PR.
    warmup_only = _session_payload("exercise-squat", [{"kind": "warmup", "weightKg": 200, "reps": 10}])
    first = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=warmup_only)
    assert first.status_code == 201
    assert first.json()["personalRecords"] == []

    modest_working_set = _session_payload("exercise-squat", [{"kind": "working", "weightKg": 60, "reps": 5}])
    second = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=modest_working_set)
    assert second.status_code == 201
    assert second.json()["personalRecords"], "a working-set PR should not be masked by an earlier warmup"


def _fresh_exercise(client: TestClient, auth_headers: dict[str, str], name: str) -> str:
    """A custom exercise with no logged history, so PR baselines start empty."""

    response = client.post(
        "/api/v1/exercises",
        headers=auth_headers,
        json={"name": name, "equipment": "barbell", "muscles": ["chest"]},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def test_a_failed_zero_rep_set_is_not_a_pr(client: TestClient, auth_headers: dict[str, str]) -> None:
    exercise_id = _fresh_exercise(client, auth_headers, "Zero-rep PR check")
    baseline = _session_payload(exercise_id, [{"kind": "working", "weightKg": 100, "reps": 5}])
    assert client.post("/api/v1/workouts/sessions", headers=auth_headers, json=baseline).status_code == 201

    # Failing a heavier attempt for 0 reps used to count as an estimated 1RM of 140 kg.
    failed_attempt = _session_payload(exercise_id, [{"kind": "working", "weightKg": 140, "reps": 0}])
    response = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=failed_attempt)
    assert response.status_code == 201
    assert response.json()["personalRecords"] == []


def test_session_volume_counts_working_sets_only(client: TestClient, auth_headers: dict[str, str]) -> None:
    exercise_id = _fresh_exercise(client, auth_headers, "Volume check")
    payload = _session_payload(
        exercise_id,
        [{"kind": "warmup", "weightKg": 40, "reps": 10}, {"kind": "working", "weightKg": 60, "reps": 5}],
    )
    response = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=payload)
    assert response.status_code == 201
    assert response.json()["volumeKg"] == 300.0  # 60 x 5; the 40 x 10 warmup is excluded
    assert response.json()["setsCompleted"] == 2


def test_today_previous_sets_matched_by_kind(client: TestClient, auth_headers: dict[str, str]) -> None:
    # The seeded plan for today is 1 warmup + 2 working sets on the bench press. Log a
    # past session with only working sets (no warmup) and check the plan's warmup slot
    # doesn't get paired with what was actually a working set's numbers (by index, it
    # would land at index 0 and grab the first working set's weight/reps).
    only_working = _session_payload(
        "exercise-bench-press",
        [
            {"kind": "working", "weightKg": 65, "reps": 6},
            {"kind": "working", "weightKg": 65, "reps": 6},
        ],
    )
    logged = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=only_working)
    assert logged.status_code == 201

    plan = client.get("/api/v1/workouts/today", headers=auth_headers).json()
    sets = plan["exercises"][0]["sets"]
    assert sets[0]["kind"] == "warmup"
    assert sets[0]["previous"] is None
    assert sets[1]["kind"] == "working"
    assert sets[1]["previous"] == {"weightKg": 65.0, "reps": 6, "rpe": None}
    assert sets[2]["kind"] == "working"
    assert sets[2]["previous"] == {"weightKg": 65.0, "reps": 6, "rpe": None}


def test_rpe_is_optional_and_round_trips(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = _session_payload(
        "exercise-bench-press",
        [
            {"kind": "working", "weightKg": 70, "reps": 8, "rpe": 8.5},
            {"kind": "working", "weightKg": 70, "reps": 8},
        ],
    )
    logged = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=payload)
    assert logged.status_code == 201

    plan = client.get("/api/v1/workouts/today", headers=auth_headers).json()
    sets = [s for s in plan["exercises"][0]["sets"] if s["kind"] == "working"]
    assert sets[0]["previous"]["rpe"] == 8.5
    assert sets[1]["previous"]["rpe"] is None


def test_rpe_rejects_non_half_step_values(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = _session_payload(
        "exercise-bench-press", [{"kind": "working", "weightKg": 70, "reps": 8, "rpe": 7.3}]
    )
    response = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=payload)
    assert response.status_code == 422


def test_get_week_plan_includes_todays_seeded_day(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/workouts/plan", headers=auth_headers)
    assert response.status_code == 200
    days = response.json()
    assert len(days) == 7
    assert {day["dayOfWeek"] for day in days} == set(range(7))
    seeded = next(day for day in days if day["plan"] is not None)
    assert seeded["plan"]["name"] == "Push day"


def test_save_and_delete_plan_day(client: TestClient, auth_headers: dict[str, str]) -> None:
    save_payload = {
        "name": "Leg day",
        "weekLabel": "Week 1",
        "estimatedMinutes": 45,
        "exercises": [
            {
                "exerciseId": "exercise-squat",
                "restSeconds": 120,
                "sets": [
                    {"kind": "warmup", "targetWeightKg": 40, "targetReps": 10},
                    {"kind": "working", "targetWeightKg": 80, "targetReps": 5},
                ],
            }
        ],
    }
    saved = client.put("/api/v1/workouts/plan/3", headers=auth_headers, json=save_payload)
    assert saved.status_code == 200
    body = saved.json()
    assert body["dayOfWeek"] == 3
    assert body["plan"]["name"] == "Leg day"
    assert len(body["plan"]["exercises"][0]["sets"]) == 2

    listed = client.get("/api/v1/workouts/plan", headers=auth_headers).json()
    day3 = next(day for day in listed if day["dayOfWeek"] == 3)
    assert day3["plan"]["name"] == "Leg day"

    # Saving the same day again must update in place, not collide with the
    # existing (owner_id, day_of_week) row.
    resaved = client.put(
        "/api/v1/workouts/plan/3", headers=auth_headers, json={**save_payload, "name": "Leg day v2"}
    )
    assert resaved.status_code == 200
    assert resaved.json()["plan"]["name"] == "Leg day v2"

    deleted = client.delete("/api/v1/workouts/plan/3", headers=auth_headers)
    assert deleted.status_code == 204

    listed_after = client.get("/api/v1/workouts/plan", headers=auth_headers).json()
    day3_after = next(day for day in listed_after if day["dayOfWeek"] == 3)
    assert day3_after["plan"] is None


def test_save_plan_day_rejects_unknown_exercise(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "name": "Leg day",
        "weekLabel": "Week 1",
        "estimatedMinutes": 45,
        "exercises": [{"exerciseId": "does-not-exist", "restSeconds": 90, "sets": [{"kind": "working"}]}],
    }
    response = client.put("/api/v1/workouts/plan/4", headers=auth_headers, json=payload)
    assert response.status_code == 404


def test_save_plan_day_rejects_out_of_range_day(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "name": "Leg day",
        "weekLabel": "Week 1",
        "estimatedMinutes": 45,
        "exercises": [{"exerciseId": "exercise-squat", "restSeconds": 90, "sets": [{"kind": "working"}]}],
    }
    response = client.put("/api/v1/workouts/plan/7", headers=auth_headers, json=payload)
    assert response.status_code == 422


def _two_exercise_session(started_minutes_ago: int, name: str) -> dict:
    """Squat first, then bench: the history must show them in that order, not alphabetically."""

    started = datetime.now(UTC) - timedelta(minutes=started_minutes_ago)
    return {
        "planId": None,
        "name": name,
        "startedAt": started.isoformat(),
        "finishedAt": (started + timedelta(minutes=30)).isoformat(),
        "exercises": [
            {
                "exerciseId": "exercise-squat",
                "name": "Barbell Squat",
                "sets": [
                    {"kind": "warmup", "weightKg": 40, "reps": 10},
                    {"kind": "working", "weightKg": 100, "reps": 5, "rpe": 8},
                ],
            },
            {
                "exerciseId": "exercise-bench-press",
                "name": "Barbell Bench Press",
                "sets": [{"kind": "working", "weightKg": 60, "reps": 8}],
            },
        ],
    }


def test_history_lists_newest_first_with_totals(client: TestClient) -> None:
    headers = register_user(client)
    assert (
        client.post(
            "/api/v1/workouts/sessions", headers=headers, json=_two_exercise_session(300, "Older")
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/workouts/sessions", headers=headers, json=_two_exercise_session(60, "Newer")
        ).status_code
        == 201
    )

    response = client.get("/api/v1/workouts/sessions", headers=headers)
    assert response.status_code == 200
    items = response.json()
    assert [item["name"] for item in items] == ["Newer", "Older"]
    newest = items[0]
    assert newest["durationSeconds"] == 1800
    assert newest["exerciseCount"] == 2
    assert newest["setsCompleted"] == 3
    # Working sets only: 100 x 5 + 60 x 8, the warmup doesn't count.
    assert newest["volumeKg"] == 980.0
    assert newest["startedAt"].endswith(("Z", "+00:00"))


def test_history_pages_with_limit_and_offset(client: TestClient) -> None:
    headers = register_user(client)
    for index in range(3):
        started = 300 - index * 60
        assert (
            client.post(
                "/api/v1/workouts/sessions",
                headers=headers,
                json=_two_exercise_session(started, f"Workout {index}"),
            ).status_code
            == 201
        )

    first = client.get("/api/v1/workouts/sessions", headers=headers, params={"limit": 2}).json()
    rest = client.get("/api/v1/workouts/sessions", headers=headers, params={"limit": 2, "offset": 2}).json()
    assert [item["name"] for item in first] == ["Workout 2", "Workout 1"]
    assert [item["name"] for item in rest] == ["Workout 0"]


def test_history_rejects_out_of_range_paging(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert (
        client.get("/api/v1/workouts/sessions", headers=auth_headers, params={"limit": 0}).status_code == 422
    )
    assert (
        client.get("/api/v1/workouts/sessions", headers=auth_headers, params={"limit": 101}).status_code
        == 422
    )
    assert (
        client.get("/api/v1/workouts/sessions", headers=auth_headers, params={"offset": -1}).status_code
        == 422
    )


def test_history_detail_keeps_exercise_order_and_set_values(client: TestClient) -> None:
    headers = register_user(client)
    created = client.post(
        "/api/v1/workouts/sessions", headers=headers, json=_two_exercise_session(60, "Legs then chest")
    )
    assert created.status_code == 201

    response = client.get(f"/api/v1/workouts/sessions/{created.json()['id']}", headers=headers)
    assert response.status_code == 200
    detail = response.json()
    assert [exercise["name"] for exercise in detail["exercises"]] == ["Barbell Squat", "Barbell Bench Press"]
    assert detail["exercises"][0]["sets"] == [
        {"kind": "warmup", "weightKg": 40.0, "reps": 10, "rpe": None},
        {"kind": "working", "weightKg": 100.0, "reps": 5, "rpe": 8.0},
    ]
    assert detail["volumeKg"] == 980.0


def test_history_is_private_to_the_owner(client: TestClient) -> None:
    owner, other = register_user(client), register_user(client)
    created = client.post("/api/v1/workouts/sessions", headers=owner, json=_two_exercise_session(60, "Mine"))
    assert created.status_code == 201

    assert client.get("/api/v1/workouts/sessions", headers=other).json() == []
    assert client.get(f"/api/v1/workouts/sessions/{created.json()['id']}", headers=other).status_code == 404
    assert client.get("/api/v1/workouts/sessions/does-not-exist", headers=owner).status_code == 404
