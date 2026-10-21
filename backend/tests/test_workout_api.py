from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.database import get_session_factory
from app.workout.catalog import SYSTEM_EXERCISES, ensure_system_exercises
from app.workout.models import Exercise
from tests.helpers import plan_every_day, register_user


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


def test_builtin_catalogue_covers_common_movements(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/exercises", headers=auth_headers, params={"limit": 100})
    assert response.status_code == 200
    library = [exercise for exercise in response.json() if exercise["source"] == "library"]
    assert len(library) == len(SYSTEM_EXERCISES)
    assert {exercise["name"] for exercise in library} >= {
        "Barbell Bench Press",
        "Lat Pulldown",
        "Dumbbell Shoulder Press",
        "Leg Press",
        "Barbell Romanian Deadlift",
        "Cable Triceps Pushdown",
        "Plank",
    }


def test_builtin_catalogue_can_be_filtered(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(
        "/api/v1/exercises",
        headers=auth_headers,
        params={"muscle": "chest", "equipment": "dumbbell", "limit": 100},
    )
    assert response.status_code == 200
    exercises = response.json()
    assert {exercise["name"] for exercise in exercises} >= {
        "Dumbbell Bench Press",
        "Incline Dumbbell Bench Press",
        "Dumbbell Chest Fly",
    }
    assert all(exercise["equipment"] == "dumbbell" for exercise in exercises)
    assert all("chest" in exercise["muscles"] for exercise in exercises)


def test_system_catalogue_install_is_idempotent(client: TestClient) -> None:
    async def reinstall_one() -> tuple[int, int, int]:
        async with get_session_factory()() as session:
            await session.execute(delete(Exercise).where(Exercise.id == "exercise-farmer-carry"))
            await session.commit()

            first = await ensure_system_exercises(session)
            second = await ensure_system_exercises(session)
            count = await session.scalar(
                select(func.count()).select_from(Exercise).where(Exercise.owner_id.is_(None))
            )
            await session.commit()
            return first, second, int(count or 0)

    assert client.portal is not None
    assert client.portal.call(reinstall_one) == (1, 0, len(SYSTEM_EXERCISES))


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


def test_finish_session_keeps_a_workout_whose_routine_no_longer_exists(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # E.g. the routine was deleted from another tab mid-workout: the sets must not be lost.
    payload = _session_payload(
        "exercise-bench-press", [{"kind": "working", "weightKg": 60, "reps": 5}], plan_id="does-not-exist"
    )
    response = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=payload)
    assert response.status_code == 201


def test_finish_session_rejects_another_users_routine(client: TestClient) -> None:
    owner, other = register_user(client), register_user(client)
    routine = client.post("/api/v1/workouts/routines", headers=owner, json=_routine_payload()).json()
    payload = _session_payload(
        "exercise-squat", [{"kind": "working", "weightKg": 60, "reps": 5}], plan_id=routine["id"]
    )
    assert client.post("/api/v1/workouts/sessions", headers=other, json=payload).status_code == 404


def test_a_routine_deleted_mid_workout_still_lets_the_workout_be_saved(client: TestClient) -> None:
    headers = register_user(client)
    routine = client.post("/api/v1/workouts/routines", headers=headers, json=_routine_payload()).json()
    client.delete(f"/api/v1/workouts/routines/{routine['id']}", headers=headers)

    payload = _session_payload(
        "exercise-squat", [{"kind": "working", "weightKg": 80, "reps": 5}], plan_id=routine["id"]
    )
    saved = client.post("/api/v1/workouts/sessions", headers=headers, json=payload)
    assert saved.status_code == 201
    assert [w["id"] for w in client.get("/api/v1/workouts/sessions", headers=headers).json()] == [
        saved.json()["id"]
    ]


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


def _routine_payload(name: str = "Leg day", exercise_id: str = "exercise-squat") -> dict:
    return {
        "name": name,
        "weekLabel": "Week 1",
        "estimatedMinutes": 45,
        "exercises": [
            {
                "exerciseId": exercise_id,
                "restSeconds": 120,
                "sets": [
                    {"kind": "warmup", "targetWeightKg": 40, "targetReps": 10},
                    {"kind": "working", "targetWeightKg": 80, "targetReps": 5},
                ],
            }
        ],
    }


def test_create_update_and_delete_a_routine(client: TestClient) -> None:
    headers = register_user(client)
    created = client.post("/api/v1/workouts/routines", headers=headers, json=_routine_payload())
    assert created.status_code == 201
    routine = created.json()
    assert routine["name"] == "Leg day"
    assert routine["scheduledDays"] == []
    assert len(routine["exercises"][0]["sets"]) == 2

    payload = {**_routine_payload("Leg day v2"), "exercises": _routine_payload()["exercises"][:1]}
    payload["exercises"][0]["sets"] = [{"kind": "working", "targetWeightKg": 90, "targetReps": 3}]
    updated = client.put(f"/api/v1/workouts/routines/{routine['id']}", headers=headers, json=payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Leg day v2"
    assert [s["targetWeightKg"] for s in updated.json()["exercises"][0]["sets"]] == [90.0]

    listed = client.get("/api/v1/workouts/routines", headers=headers).json()
    assert [r["name"] for r in listed] == ["Leg day v2"]

    assert client.delete(f"/api/v1/workouts/routines/{routine['id']}", headers=headers).status_code == 204
    assert client.get("/api/v1/workouts/routines", headers=headers).json() == []
    assert client.delete(f"/api/v1/workouts/routines/{routine['id']}", headers=headers).status_code == 404


def test_one_routine_can_be_scheduled_on_several_days(client: TestClient) -> None:
    headers = register_user(client)
    routine = client.post("/api/v1/workouts/routines", headers=headers, json=_routine_payload("Push")).json()

    for day in (0, 4):
        assigned = client.put(
            f"/api/v1/workouts/plan/{day}", headers=headers, json={"routineId": routine["id"]}
        )
        assert assigned.status_code == 200
        assert assigned.json()["dayOfWeek"] == day
        assert assigned.json()["plan"]["name"] == "Push"

    week = client.get("/api/v1/workouts/plan", headers=headers).json()
    assert [d["dayOfWeek"] for d in week if d["plan"]] == [0, 4]
    assert client.get("/api/v1/workouts/routines", headers=headers).json()[0]["scheduledDays"] == [0, 4]


def test_editing_a_routine_changes_every_day_it_is_scheduled_on(client: TestClient) -> None:
    headers = register_user(client)
    routine = client.post("/api/v1/workouts/routines", headers=headers, json=_routine_payload("Push")).json()
    for day in (1, 3):
        client.put(f"/api/v1/workouts/plan/{day}", headers=headers, json={"routineId": routine["id"]})

    client.put(
        f"/api/v1/workouts/routines/{routine['id']}", headers=headers, json=_routine_payload("Push v2")
    )

    week = client.get("/api/v1/workouts/plan", headers=headers).json()
    assert [d["plan"]["name"] for d in week if d["plan"]] == ["Push v2", "Push v2"]


def test_assigning_a_day_again_replaces_its_routine(client: TestClient) -> None:
    headers = register_user(client)
    push = client.post("/api/v1/workouts/routines", headers=headers, json=_routine_payload("Push")).json()
    pull = client.post("/api/v1/workouts/routines", headers=headers, json=_routine_payload("Pull")).json()

    client.put("/api/v1/workouts/plan/2", headers=headers, json={"routineId": push["id"]})
    client.put("/api/v1/workouts/plan/2", headers=headers, json={"routineId": pull["id"]})

    day = next(d for d in client.get("/api/v1/workouts/plan", headers=headers).json() if d["dayOfWeek"] == 2)
    assert day["plan"]["name"] == "Pull"
    routines = {
        r["name"]: r["scheduledDays"] for r in client.get("/api/v1/workouts/routines", headers=headers).json()
    }
    assert routines == {"Push": [], "Pull": [2]}


def test_clearing_a_day_keeps_the_routine(client: TestClient) -> None:
    headers = register_user(client)
    routine = client.post("/api/v1/workouts/routines", headers=headers, json=_routine_payload()).json()
    client.put("/api/v1/workouts/plan/3", headers=headers, json={"routineId": routine["id"]})

    assert client.delete("/api/v1/workouts/plan/3", headers=headers).status_code == 204

    day = next(d for d in client.get("/api/v1/workouts/plan", headers=headers).json() if d["dayOfWeek"] == 3)
    assert day["plan"] is None
    assert [r["scheduledDays"] for r in client.get("/api/v1/workouts/routines", headers=headers).json()] == [
        []
    ]


def test_deleting_a_routine_takes_it_off_the_schedule_but_keeps_logged_workouts(client: TestClient) -> None:
    headers = register_user(client)
    routine = client.post("/api/v1/workouts/routines", headers=headers, json=_routine_payload()).json()
    client.put("/api/v1/workouts/plan/5", headers=headers, json={"routineId": routine["id"]})
    session = _session_payload(
        "exercise-squat", [{"kind": "working", "weightKg": 80, "reps": 5}], plan_id=routine["id"]
    )
    logged = client.post("/api/v1/workouts/sessions", headers=headers, json=session)
    assert logged.status_code == 201

    assert client.delete(f"/api/v1/workouts/routines/{routine['id']}", headers=headers).status_code == 204

    day = next(d for d in client.get("/api/v1/workouts/plan", headers=headers).json() if d["dayOfWeek"] == 5)
    assert day["plan"] is None
    assert [w["id"] for w in client.get("/api/v1/workouts/sessions", headers=headers).json()] == [
        logged.json()["id"]
    ]


def test_today_follows_the_schedule(client: TestClient) -> None:
    headers = register_user(client)
    assert client.get("/api/v1/workouts/today", headers=headers).json() is None
    plan_every_day(client, headers)
    assert client.get("/api/v1/workouts/today", headers=headers).json()["name"] == "Full body"


def test_routines_are_private_to_their_owner(client: TestClient) -> None:
    owner, other = register_user(client), register_user(client)
    routine = client.post("/api/v1/workouts/routines", headers=owner, json=_routine_payload()).json()

    assert client.get("/api/v1/workouts/routines", headers=other).json() == []
    assert (
        client.put(
            f"/api/v1/workouts/routines/{routine['id']}", headers=other, json=_routine_payload("X")
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/workouts/routines/{routine['id']}", headers=other).status_code == 404
    assert (
        client.put("/api/v1/workouts/plan/1", headers=other, json={"routineId": routine["id"]}).status_code
        == 404
    )
    assert client.get("/api/v1/workouts/routines", headers=owner).json()[0]["name"] == "Leg day"


def test_a_routine_needs_known_exercises(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = _routine_payload(exercise_id="does-not-exist")
    assert client.post("/api/v1/workouts/routines", headers=auth_headers, json=payload).status_code == 404


def test_assign_day_rejects_out_of_range_day_and_unknown_routine(client: TestClient) -> None:
    headers = register_user(client)
    routine = client.post("/api/v1/workouts/routines", headers=headers, json=_routine_payload()).json()
    assert (
        client.put("/api/v1/workouts/plan/7", headers=headers, json={"routineId": routine["id"]}).status_code
        == 422
    )
    assert (
        client.put("/api/v1/workouts/plan/1", headers=headers, json={"routineId": "nope"}).status_code == 404
    )
    assert client.put("/api/v1/workouts/plan/1", headers=headers, json={}).status_code == 422


def test_routines_per_user_are_capped(client: TestClient) -> None:
    headers = register_user(client)
    for index in range(50):
        assert (
            client.post(
                "/api/v1/workouts/routines", headers=headers, json=_routine_payload(f"R{index}")
            ).status_code
            == 201
        )
    over = client.post("/api/v1/workouts/routines", headers=headers, json=_routine_payload("One too many"))
    assert over.status_code == 422


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
    assert [exercise["exerciseId"] for exercise in detail["exercises"]] == [
        "exercise-squat",
        "exercise-bench-press",
    ]
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


def test_failure_and_drop_sets_count_toward_volume_and_prs(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    exercise_id = _fresh_exercise(client, auth_headers, "Set kind check")
    payload = _session_payload(
        exercise_id,
        [
            {"kind": "warmup", "weightKg": 40, "reps": 10},
            {"kind": "working", "weightKg": 60, "reps": 5},
            {"kind": "failure", "weightKg": 60, "reps": 8},
            {"kind": "drop", "weightKg": 40, "reps": 10},
        ],
    )
    response = client.post("/api/v1/workouts/sessions", headers=auth_headers, json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["volumeKg"] == 1180.0  # 60x5 + 60x8 + 40x10; the warmup is excluded
    assert body["setsCompleted"] == 4
    assert body["personalRecords"], "the failure set (60 x 8) is the best estimated 1RM"

    detail = client.get(f"/api/v1/workouts/sessions/{body['id']}", headers=auth_headers).json()
    assert [s["kind"] for s in detail["exercises"][0]["sets"]] == ["warmup", "working", "failure", "drop"]


def test_unknown_set_kind_is_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = _session_payload("exercise-squat", [{"kind": "superset", "weightKg": 60, "reps": 5}])
    assert client.post("/api/v1/workouts/sessions", headers=auth_headers, json=payload).status_code == 422


def test_update_session_replaces_name_and_sets(client: TestClient) -> None:
    headers = register_user(client)
    created = client.post(
        "/api/v1/workouts/sessions", headers=headers, json=_two_exercise_session(60, "Typo")
    )
    session_id = created.json()["id"]

    corrected = {
        "name": "Legs then chest",
        "exercises": [
            {
                "exerciseId": "exercise-bench-press",
                "name": "Barbell Bench Press",
                "sets": [
                    {"kind": "working", "weightKg": 62.5, "reps": 8, "rpe": 8.5},
                    {"kind": "drop", "weightKg": 40, "reps": 12},
                ],
            }
        ],
    }
    response = client.put(f"/api/v1/workouts/sessions/{session_id}", headers=headers, json=corrected)
    assert response.status_code == 200
    detail = response.json()
    assert detail["name"] == "Legs then chest"
    assert detail["durationSeconds"] == 1800, "start and finish times are kept"
    assert detail["exerciseCount"] == 1
    assert detail["volumeKg"] == 500.0 + 480.0  # 62.5 x 8 + 40 x 12
    assert detail["exercises"][0]["sets"][1] == {"kind": "drop", "weightKg": 40.0, "reps": 12, "rpe": None}

    listed = client.get("/api/v1/workouts/sessions", headers=headers).json()
    assert [item["id"] for item in listed] == [session_id]
    assert listed[0]["setsCompleted"] == 2


def test_update_session_rejects_unknown_exercise_and_leaves_the_workout_alone(client: TestClient) -> None:
    headers = register_user(client)
    session_id = client.post(
        "/api/v1/workouts/sessions", headers=headers, json=_two_exercise_session(60, "Keep me")
    ).json()["id"]

    bad = {
        "name": "Changed",
        "exercises": [
            {"exerciseId": "nope", "name": "X", "sets": [{"kind": "working", "weightKg": 1, "reps": 1}]}
        ],
    }
    assert client.put(f"/api/v1/workouts/sessions/{session_id}", headers=headers, json=bad).status_code == 404

    detail = client.get(f"/api/v1/workouts/sessions/{session_id}", headers=headers).json()
    assert detail["name"] == "Keep me"
    assert detail["setsCompleted"] == 3


def test_update_session_requires_at_least_one_set(client: TestClient) -> None:
    headers = register_user(client)
    session_id = client.post(
        "/api/v1/workouts/sessions", headers=headers, json=_two_exercise_session(60, "A")
    ).json()["id"]
    empty = {
        "name": "A",
        "exercises": [{"exerciseId": "exercise-squat", "name": "Barbell Squat", "sets": []}],
    }
    assert (
        client.put(f"/api/v1/workouts/sessions/{session_id}", headers=headers, json=empty).status_code == 422
    )


def test_delete_session_removes_it_from_history(client: TestClient) -> None:
    headers = register_user(client)
    session_id = client.post(
        "/api/v1/workouts/sessions", headers=headers, json=_two_exercise_session(60, "Gone")
    ).json()["id"]

    assert client.delete(f"/api/v1/workouts/sessions/{session_id}", headers=headers).status_code == 204
    assert client.get("/api/v1/workouts/sessions", headers=headers).json() == []
    assert client.get(f"/api/v1/workouts/sessions/{session_id}", headers=headers).status_code == 404
    assert client.delete(f"/api/v1/workouts/sessions/{session_id}", headers=headers).status_code == 404


def test_deleting_a_session_gives_the_pr_back(client: TestClient) -> None:
    headers = register_user(client)
    exercise_id = _fresh_exercise(client, headers, "PR after delete")
    heavy = client.post(
        "/api/v1/workouts/sessions",
        headers=headers,
        json=_session_payload(exercise_id, [{"kind": "working", "weightKg": 100, "reps": 5}]),
    ).json()["id"]
    client.delete(f"/api/v1/workouts/sessions/{heavy}", headers=headers)

    lighter = client.post(
        "/api/v1/workouts/sessions",
        headers=headers,
        json=_session_payload(exercise_id, [{"kind": "working", "weightKg": 60, "reps": 5}]),
    )
    assert lighter.json()["personalRecords"], "the deleted session no longer sets the bar"


def test_other_users_cannot_edit_or_delete_a_session(client: TestClient) -> None:
    owner, other = register_user(client), register_user(client)
    session_id = client.post(
        "/api/v1/workouts/sessions", headers=owner, json=_two_exercise_session(60, "Mine")
    ).json()["id"]
    edit = {
        "name": "Hijacked",
        "exercises": [
            {
                "exerciseId": "exercise-squat",
                "name": "Barbell Squat",
                "sets": [{"kind": "working", "weightKg": 1, "reps": 1}],
            }
        ],
    }

    assert client.put(f"/api/v1/workouts/sessions/{session_id}", headers=other, json=edit).status_code == 404
    assert client.delete(f"/api/v1/workouts/sessions/{session_id}", headers=other).status_code == 404
    assert client.get(f"/api/v1/workouts/sessions/{session_id}", headers=owner).json()["name"] == "Mine"
