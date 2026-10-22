"""Versioned nutrition targets: history, per-day judging, and check-in changes."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.core.database import get_session_factory
from app.profile.models import NutritionTarget, TargetSource
from app.profile.repository import ProfileRepository
from tests.helpers import register_user

TARGETS = "/api/v1/nutrition/targets"
CHECK_INS = "/api/v1/coach/check-ins"


def _set_targets(client: TestClient, headers: dict[str, str], calories: int) -> None:
    response = client.put(
        TARGETS, headers=headers, json={"calories": calories, "protein": 150, "carbs": 200, "fat": 60}
    )
    assert response.status_code == 200


def _history(client: TestClient, headers: dict[str, str]) -> list[dict]:
    response = client.get(f"{TARGETS}/history", headers=headers)
    assert response.status_code == 200
    return list(response.json())


def _backdate(client: TestClient, headers: dict[str, str], version: int, effective: date) -> None:
    """Move one version's effective date into the past, as if it had been set back then."""

    owner_id = client.get("/api/v1/users/me", headers=headers).json()["id"]

    async def move() -> None:
        async with get_session_factory()() as session:
            await session.execute(
                update(NutritionTarget)
                .where(NutritionTarget.owner_id == owner_id, NutritionTarget.version == version)
                .values(effective_date=effective)
            )
            await session.commit()

    assert client.portal is not None
    client.portal.call(move)


def _log(client: TestClient, headers: dict[str, str], days_ago: int, calories: int) -> None:
    response = client.post(
        "/api/v1/food-log/entries",
        headers=headers,
        json={
            "date": (date.today() - timedelta(days=days_ago)).isoformat(),
            "meal": "lunch",
            "name": "Meal",
            "amountLabel": "1 plate",
            "source": "quick-add",
            "calories": calories,
            "protein": 100,
            "carbs": 200,
            "fat": 60,
        },
    )
    assert response.status_code == 201


def test_a_new_user_starts_with_one_initial_version(client: TestClient) -> None:
    headers = register_user(client)
    history = _history(client, headers)
    assert [(v["version"], v["source"]) for v in history] == [(1, "initial")]
    assert history[0]["effectiveDate"] == date.today().isoformat()
    assert history[0]["changedAt"].endswith(("Z", "+00:00"))


def test_each_change_adds_a_version_and_keeps_the_old_ones(client: TestClient) -> None:
    headers = register_user(client)
    _set_targets(client, headers, 2000)
    _set_targets(client, headers, 2100)

    history = _history(client, headers)
    assert [(v["version"], v["calories"], v["source"]) for v in history] == [
        (3, 2100, "manual"),
        (2, 2000, "manual"),
        (1, 2200, "initial"),
    ]
    assert client.get(TARGETS, headers=headers).json()["calories"] == 2100


def test_saving_unchanged_targets_adds_no_version(client: TestClient) -> None:
    headers = register_user(client)
    _set_targets(client, headers, 2000)
    _set_targets(client, headers, 2000)
    assert len(_history(client, headers)) == 2


def test_changing_the_target_today_does_not_rewrite_earlier_days(client: TestClient) -> None:
    headers = register_user(client)
    _set_targets(client, headers, 2000)
    _backdate(client, headers, version=1, effective=date.today() - timedelta(days=30))
    _backdate(client, headers, version=2, effective=date.today() - timedelta(days=30))
    _log(client, headers, days_ago=2, calories=2000)
    _log(client, headers, days_ago=1, calories=2000)

    before = client.get("/api/v1/nutrition/daily-calories", headers=headers, params={"days": 7}).json()
    assert before["targetGapKcal"] == 0

    _set_targets(client, headers, 2500)  # from today on

    after = client.get("/api/v1/nutrition/daily-calories", headers=headers, params={"days": 7}).json()
    assert after["targetGapKcal"] == 0, (
        "yesterday's 2000 kcal is still judged against yesterday's 2000 target"
    )
    assert after["targetCalories"] == 2500
    # From the first day logged (2 days ago): the account is new.
    assert [day["targetCalories"] for day in after["days"]] == [2000] * 2 + [2500]

    progress = client.get("/api/v1/progress", headers=headers, params={"range": "1M"}).json()
    assert progress["logging"]["targetAdherencePercent"] == 100.0
    assert progress["logging"]["targetGapKcal"] == 0


def _week_for_a_check_in(client: TestClient, headers: dict[str, str]) -> dict:
    for days_ago in range(7):
        _log(client, headers, days_ago=days_ago, calories=2000)
    for days_ago, weight in ((6, 80), (0, 78)):
        client.post(
            "/api/v1/body/weigh-ins",
            headers=headers,
            json={"date": (date.today() - timedelta(days=days_ago)).isoformat(), "weightKg": weight},
        )
    client.post(CHECK_INS, headers={**headers, "Idempotency-Key": "versions"})
    check_in = client.get(f"{CHECK_INS}/current", headers=headers).json()
    assert len(check_in["proposals"]) == 1
    return dict(check_in)


def _decide(client: TestClient, headers: dict[str, str], check_in: dict, decision: str = "apply"):
    proposal_id = check_in["proposals"][0]["id"]
    return client.post(
        f"{CHECK_INS}/{check_in['id']}/proposals/{proposal_id}/decision",
        headers=headers,
        json={"decision": decision},
    )


def test_an_applied_proposal_is_recorded_as_a_check_in_version(client: TestClient) -> None:
    headers = register_user(client)
    check_in = _week_for_a_check_in(client, headers)
    proposed = round(check_in["proposals"][0]["changes"][0]["after"])

    assert _decide(client, headers, check_in).status_code == 200

    newest = _history(client, headers)[0]
    assert (newest["version"], newest["calories"], newest["source"]) == (2, proposed, "check-in")
    assert newest["effectiveDate"] == date.today().isoformat()


def test_a_proposal_is_refused_once_the_targets_changed_after_its_check_in(client: TestClient) -> None:
    headers = register_user(client)
    check_in = _week_for_a_check_in(client, headers)
    _set_targets(client, headers, 2300)  # the proposal was worked out from the old target

    response = _decide(client, headers, check_in)

    assert response.status_code == 409
    assert "out of date" in response.json()["detail"]
    assert client.get(TARGETS, headers=headers).json()["calories"] == 2300
    current = client.get(f"{CHECK_INS}/current", headers=headers).json()
    assert current["proposals"][0]["status"] == "pending", "still pending, so it can be rejected"
    assert _decide(client, headers, check_in, "reject").status_code == 200


def test_target_history_is_private(client: TestClient) -> None:
    owner, other = register_user(client), register_user(client)
    _set_targets(client, owner, 1900)
    assert [v["calories"] for v in _history(client, other)] == [2200]


def test_resaving_targets_finer_than_stored_adds_no_version(client: TestClient) -> None:
    headers = register_user(client)
    body = {"calories": 2000, "protein": 150.25, "carbs": 200, "fat": 60}
    first = client.put(TARGETS, headers=headers, json=body)
    assert first.json()["protein"] == 150.3  # stored to one decimal
    client.put(TARGETS, headers=headers, json=body)
    assert len(_history(client, headers)) == 2


def test_a_change_decided_on_outdated_targets_is_refused_not_written_over(client: TestClient) -> None:
    """Two writers both read version 2; the second to save must not quietly become version 4."""

    headers = register_user(client)
    _set_targets(client, headers, 2000)
    owner_id = client.get("/api/v1/users/me", headers=headers).json()["id"]

    async def write(session_factory, previous: NutritionTarget | None, calories: int) -> str:
        async with session_factory() as session:
            try:
                await ProfileRepository(session).add_target_version(
                    owner_id,
                    previous=previous,
                    calories=calories,
                    protein=150,
                    carbs=200,
                    fat=60,
                    effective_date=date.today(),
                    source=TargetSource.MANUAL,
                )
                await session.commit()
            except IntegrityError:
                return "refused"
            return "written"

    async def race() -> tuple[str, str]:
        factory = get_session_factory()
        async with factory() as session:
            stale = await ProfileRepository(session).current_targets(owner_id)  # both writers read version 2
        return await write(factory, stale, 2100), await write(factory, stale, 1800)

    assert client.portal is not None
    assert client.portal.call(race) == ("written", "refused")
    assert client.get(TARGETS, headers=headers).json()["calories"] == 2100


def _zone_on_another_day_than_utc() -> tuple[str, date]:
    """A timezone whose calendar day differs from UTC's right now, and its date."""

    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(UTC)
    zone = "Etc/GMT-14" if now.hour >= 10 else "Etc/GMT+12"  # UTC+14 or UTC-12
    return zone, now.astimezone(ZoneInfo(zone)).date()


def test_a_new_accounts_starting_targets_are_dated_by_its_own_timezone(client: TestClient) -> None:
    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "New", "email": f"{uuid.uuid4().hex}@example.com", "password": "long-enough-pw"},
    )
    headers = {"Authorization": f"Bearer {registered.json()['accessToken']}"}
    client.get("/api/v1/profile", headers=headers)  # provisioned before the browser sends its zone
    zone, local_day = _zone_on_another_day_than_utc()

    client.put("/api/v1/profile/timezone", headers=headers, json={"timezone": zone})

    assert _history(client, headers)[0]["effectiveDate"] == local_day.isoformat()


def test_a_changed_timezone_doesnt_redate_targets_the_user_already_changed(client: TestClient) -> None:
    headers = register_user(client, timezone="UTC")
    _set_targets(client, headers, 2000)
    dates = [v["effectiveDate"] for v in _history(client, headers)]
    zone, _ = _zone_on_another_day_than_utc()

    client.put("/api/v1/profile/timezone", headers=headers, json={"timezone": zone})

    assert [v["effectiveDate"] for v in _history(client, headers)] == dates


def test_only_the_first_timezone_sync_redates_the_starting_targets(client: TestClient) -> None:
    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "New", "email": f"{uuid.uuid4().hex}@example.com", "password": "long-enough-pw"},
    )
    headers = {"Authorization": f"Bearer {registered.json()['accessToken']}"}
    client.get("/api/v1/profile", headers=headers)
    zone, local_day = _zone_on_another_day_than_utc()
    client.put("/api/v1/profile/timezone", headers=headers, json={"timezone": zone})
    assert _history(client, headers)[0]["effectiveDate"] == local_day.isoformat()

    # Travelling (or a VPN) later the same day doesn't move it again.
    client.put("/api/v1/profile/timezone", headers=headers, json={"timezone": "UTC"})
    assert _history(client, headers)[0]["effectiveDate"] == local_day.isoformat()
