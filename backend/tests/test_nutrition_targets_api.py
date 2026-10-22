"""Versioned nutrition targets: history, per-day judging, and check-in changes."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.core.database import get_session_factory
from app.profile.models import NutritionTarget, TargetSource
from app.profile.repository import ProfileRepository
from tests.helpers import (
    current_check_in,
    decide,
    log_meal,
    register_user,
    start_check_in,
    target_history,
    week_with_a_proposal,
)

TARGETS = "/api/v1/nutrition/targets"


def _set_targets(client: TestClient, headers: dict[str, str], calories: int) -> None:
    response = client.put(
        TARGETS, headers=headers, json={"calories": calories, "protein": 150, "carbs": 200, "fat": 60}
    )
    assert response.status_code == 200


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


def test_a_new_user_starts_with_one_initial_version(client: TestClient) -> None:
    headers = register_user(client)
    history = target_history(client, headers)
    assert [(v["version"], v["source"]) for v in history] == [(1, "initial")]
    assert history[0]["effectiveDate"] == date.today().isoformat()
    assert history[0]["changedAt"].endswith(("Z", "+00:00"))


def test_each_change_adds_a_version_and_keeps_the_old_ones(client: TestClient) -> None:
    headers = register_user(client)
    _set_targets(client, headers, 2000)
    _set_targets(client, headers, 2100)

    history = target_history(client, headers)
    assert [(v["version"], v["calories"], v["source"]) for v in history] == [
        (3, 2100, "manual"),
        (2, 2000, "manual"),
        (1, 2200, "initial"),
    ]
    assert client.get(TARGETS, headers=headers).json()["calories"] == 2100


def test_history_shows_the_latest_versions(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.profile.service.MAX_TARGET_HISTORY", 2)
    headers = register_user(client)
    _set_targets(client, headers, 2100)
    _set_targets(client, headers, 2200)

    assert [(row["version"], row["calories"]) for row in target_history(client, headers)] == [
        (3, 2200),
        (2, 2100),
    ]


def test_saving_unchanged_targets_adds_no_version(client: TestClient) -> None:
    headers = register_user(client)
    _set_targets(client, headers, 2000)
    _set_targets(client, headers, 2000)
    assert len(target_history(client, headers)) == 2


def test_changing_the_target_today_does_not_rewrite_earlier_days(client: TestClient) -> None:
    headers = register_user(client)
    _set_targets(client, headers, 2000)
    _backdate(client, headers, version=1, effective=date.today() - timedelta(days=30))
    _backdate(client, headers, version=2, effective=date.today() - timedelta(days=30))
    log_meal(client, headers, days_ago=2, calories=2000)
    log_meal(client, headers, days_ago=1, calories=2000)

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
    week_with_a_proposal(client, headers)
    start_check_in(client, headers, "versions")
    check_in = current_check_in(client, headers)
    assert len(check_in["proposals"]) == 1
    return dict(check_in)


def test_an_applied_proposal_is_recorded_as_a_check_in_version(client: TestClient) -> None:
    headers = register_user(client)
    check_in = _week_for_a_check_in(client, headers)
    proposed = round(check_in["proposals"][0]["changes"][0]["after"])

    assert decide(client, headers, check_in, {"decision": "apply"}).status_code == 200

    newest = target_history(client, headers)[0]
    assert (newest["version"], newest["calories"], newest["source"]) == (2, proposed, "check-in")
    assert newest["effectiveDate"] == date.today().isoformat()


def test_a_proposal_is_refused_once_the_targets_changed_after_its_check_in(client: TestClient) -> None:
    headers = register_user(client)
    check_in = _week_for_a_check_in(client, headers)
    _set_targets(client, headers, 2300)  # the proposal was worked out from the old target

    response = decide(client, headers, check_in, {"decision": "apply"})

    assert response.status_code == 409
    assert "out of date" in response.json()["detail"]
    assert client.get(TARGETS, headers=headers).json()["calories"] == 2300
    current = current_check_in(client, headers)
    assert current["proposals"][0]["status"] == "pending", "still pending, so it can be rejected"
    assert decide(client, headers, check_in, {"decision": "reject"}).status_code == 200


def test_target_history_is_private(client: TestClient) -> None:
    owner, other = register_user(client), register_user(client)
    _set_targets(client, owner, 1900)
    assert [v["calories"] for v in target_history(client, other)] == [2200]


def test_resaving_targets_finer_than_stored_adds_no_version(client: TestClient) -> None:
    headers = register_user(client)
    body = {"calories": 2000, "protein": 150.25, "carbs": 200, "fat": 60}
    first = client.put(TARGETS, headers=headers, json=body)
    assert first.json()["protein"] == 150.3  # stored to one decimal
    client.put(TARGETS, headers=headers, json=body)
    assert len(target_history(client, headers)) == 2


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

    assert target_history(client, headers)[0]["effectiveDate"] == local_day.isoformat()


def test_a_changed_timezone_doesnt_redate_targets_the_user_already_changed(client: TestClient) -> None:
    headers = register_user(client, timezone="UTC")
    _set_targets(client, headers, 2000)
    dates = [v["effectiveDate"] for v in target_history(client, headers)]
    zone, _ = _zone_on_another_day_than_utc()

    client.put("/api/v1/profile/timezone", headers=headers, json={"timezone": zone})

    assert [v["effectiveDate"] for v in target_history(client, headers)] == dates


def test_only_the_first_timezone_sync_redates_the_starting_targets(client: TestClient) -> None:
    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "New", "email": f"{uuid.uuid4().hex}@example.com", "password": "long-enough-pw"},
    )
    headers = {"Authorization": f"Bearer {registered.json()['accessToken']}"}
    client.get("/api/v1/profile", headers=headers)
    zone, local_day = _zone_on_another_day_than_utc()
    client.put("/api/v1/profile/timezone", headers=headers, json={"timezone": zone})
    assert target_history(client, headers)[0]["effectiveDate"] == local_day.isoformat()

    # Travelling (or a VPN) later the same day doesn't move it again.
    client.put("/api/v1/profile/timezone", headers=headers, json={"timezone": "UTC"})
    assert target_history(client, headers)[0]["effectiveDate"] == local_day.isoformat()
