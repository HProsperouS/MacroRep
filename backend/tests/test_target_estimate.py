"""Estimating starting targets: Mifflin-St Jeor, an activity factor, the weekly goal, macros."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.analytics.energy import ActivityLevel, Sex, age_on, estimate_targets, resting_energy
from app.analytics.nutrition import KCAL_PER_KG_BODY_MASS
from tests.helpers import GUIDE, ONBOARDING, register_user

ESTIMATE = "/api/v1/nutrition/targets/estimate"
LIMITS: dict[str, int] = {
    "min_calories": 1_000,
    "max_calories": 6_000,
    "max_protein_g": 500,
    "max_carbs_g": 1_000,
}


def _years_ago(years: int) -> str:
    today = date.today()
    return today.replace(year=today.year - years, day=min(today.day, 28)).isoformat()


DETAILS: dict[str, Any] = {
    "heightCm": 180,
    "weightKg": 80,
    "dateOfBirth": _years_ago(30),
    "sex": "male",
    "activityLevel": "moderate",
    "goal": "lose",
    "weeklyRateKg": -0.5,
}


def test_resting_energy_is_mifflin_st_jeor() -> None:
    assert resting_energy(80, 180, 30, Sex.MALE) == 10 * 80 + 6.25 * 180 - 5 * 30 + 5
    assert resting_energy(60, 165, 25, Sex.FEMALE) == 10 * 60 + 6.25 * 165 - 5 * 25 - 161


def test_age_counts_whole_years_up_to_the_birthday() -> None:
    assert age_on(date(1995, 6, 15), date(2025, 6, 14)) == 29
    assert age_on(date(1995, 6, 15), date(2025, 6, 15)) == 30


def test_a_cut_takes_the_weekly_loss_off_maintenance() -> None:
    estimate = estimate_targets(
        weight_kg=80,
        height_cm=180,
        age=30,
        sex=Sex.MALE,
        activity=ActivityLevel.MODERATE,
        goal="lose",
        weekly_rate_kg=-0.5,
        **LIMITS,
    )

    resting = 10 * 80 + 6.25 * 180 - 5 * 30 + 5  # 1,780
    assert (estimate.resting, estimate.maintenance) == (1780, round(resting * 1.55))
    assert estimate.adjustment == round(-0.5 * KCAL_PER_KG_BODY_MASS / 7)  # -550
    assert estimate.calories == 2200, "2,209 rounded to 50 kcal"
    assert (estimate.protein, estimate.fat, estimate.carbs) == (160, 61, 253), (
        "2 g/kg, 25% fat, carbs the rest"
    )
    assert abs(estimate.protein * 4 + estimate.carbs * 4 + estimate.fat * 9 - estimate.calories) <= 5


def test_maintaining_ignores_the_rate() -> None:
    common: dict[str, Any] = {"weight_kg": 60, "height_cm": 165, "age": 25, "sex": Sex.FEMALE, **LIMITS}
    maintain = estimate_targets(activity=ActivityLevel.LIGHT, goal="maintain", weekly_rate_kg=0.5, **common)

    assert maintain.adjustment == 0
    assert maintain.calories == round(maintain.maintenance / 50) * 50


def test_the_estimate_stays_within_the_target_range_and_its_macros_fit() -> None:
    # A heavy, inactive person losing fast: maintenance minus the loss is below the floor.
    estimate = estimate_targets(
        weight_kg=200,
        height_cm=150,
        age=90,
        sex=Sex.FEMALE,
        activity=ActivityLevel.SEDENTARY,
        goal="lose",
        weekly_rate_kg=-2,
        **LIMITS,
    )

    assert estimate.calories == 1_000
    assert estimate.protein * 4 + estimate.fat * 9 <= estimate.calories, "protein capped so the macros fit"
    assert estimate.carbs >= 0


def test_carbs_stay_within_the_target_limit_at_the_top_of_the_range() -> None:
    # A light person gaining very fast: calories hit the 6,000 cap, and carbs would pass 1,000 g.
    estimate = estimate_targets(
        weight_kg=60,
        height_cm=170,
        age=25,
        sex=Sex.MALE,
        activity=ActivityLevel.VERY,
        goal="gain",
        weekly_rate_kg=3.5,
        **LIMITS,
    )

    assert estimate.calories == 6_000
    assert estimate.carbs == 1_000


def test_the_guide_gets_an_estimate_from_what_it_has_so_far(client: TestClient) -> None:
    headers = register_user(client)

    response = client.post(ESTIMATE, headers=headers, json=DETAILS)

    assert response.status_code == 200
    assert response.json() == {
        "calories": 2200,
        "protein": 160,
        "carbs": 253,
        "fat": 61,
        "resting": 1780,
        "maintenance": 2759,
        "adjustment": -550,
    }
    assert len(client.get("/api/v1/nutrition/targets/history", headers=headers).json()) == 1, "nothing saved"


@pytest.mark.parametrize(
    "change",
    [
        {"dateOfBirth": _years_ago(11)},
        {"dateOfBirth": _years_ago(102)},
        {"sex": "other"},
        {"activityLevel": "extreme"},
        {"heightCm": 99},
    ],
    ids=["too-young", "too-old", "unknown-sex", "unknown-activity", "too-short"],
)
def test_an_estimate_needs_details_the_formula_is_meant_for(
    client: TestClient, change: dict[str, Any]
) -> None:
    headers = register_user(client)
    assert client.post(ESTIMATE, headers=headers, json={**DETAILS, **change}).status_code == 422


def test_estimating_for_the_guide_creates_nothing(client: TestClient) -> None:
    from sqlalchemy import func, select

    from app.core.database import get_session_factory
    from app.profile.models import Profile

    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "New", "email": "estimate-only@example.com", "password": "long-enough-pw"},
    ).json()
    headers = {"Authorization": f"Bearer {registered['accessToken']}"}
    user_id = client.get("/api/v1/users/me", headers=headers).json()["id"]

    assert client.post(ESTIMATE, headers=headers, json=DETAILS).status_code == 200

    async def profiles() -> int:
        async with get_session_factory()() as session:
            count = await session.scalar(
                select(func.count()).select_from(Profile).where(Profile.user_id == user_id)
            )
            return int(count or 0)

    assert client.portal is not None
    assert client.portal.call(profiles) == 0


def test_the_profile_page_estimates_from_the_saved_profile_and_latest_weight(client: TestClient) -> None:
    headers = register_user(client)
    missing = client.get(ESTIMATE, headers=headers)
    assert missing.status_code == 409, "a new profile has no birth date, sex or activity level yet"

    assert client.post(ONBOARDING, headers=headers, json=GUIDE).status_code == 200
    estimate = client.get(ESTIMATE, headers=headers)

    assert estimate.status_code == 200
    from_details = client.post(
        ESTIMATE,
        headers=headers,
        json={
            "heightCm": GUIDE["heightCm"],
            "weightKg": GUIDE["weightKg"],
            "dateOfBirth": GUIDE["dateOfBirth"],
            "sex": GUIDE["sex"],
            "activityLevel": GUIDE["activityLevel"],
            "goal": GUIDE["goal"],
            "weeklyRateKg": GUIDE["weeklyRateKg"],
        },
    ).json()
    assert estimate.json() == from_details
    assert client.get("/api/v1/nutrition/targets", headers=headers).json() == GUIDE["targets"], (
        "nothing saved"
    )


def test_saving_a_profile_needs_the_estimates_details(client: TestClient) -> None:
    headers = register_user(client)
    profile = {key: value for key, value in GUIDE.items() if key not in ("weightKg", "targets")}

    assert client.put("/api/v1/profile", headers=headers, json=profile).json()["sex"] == "female"
    for missing in ("dateOfBirth", "sex", "activityLevel"):
        incomplete = {key: value for key, value in profile.items() if key != missing}
        assert client.put("/api/v1/profile", headers=headers, json=incomplete).status_code == 422
