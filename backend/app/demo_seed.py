"""Idempotent local demo data used only when ``SEED_DEMO_DATA`` is enabled.

Seeds one user (id ``USR-DEMO``) that local development can sign in as, either
by posting the email/password below to `/api/v1/auth/login` or by sending
`X-Preview-Actor-Id: USR-DEMO` while `PREVIEW_AUTH_ENABLED` is on.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.energy import ActivityLevel, Sex
from app.auth.security import hash_password
from app.coach.agents.graph import run_agents
from app.coach.agents.model import FakeCoachModel
from app.coach.models import CheckIn, Proposal
from app.core.database import get_session_factory
from app.food.models import Food
from app.identity.models import User, UserStatus
from app.profile.models import ExperienceLevel, Goal, NutritionTarget, Profile, TargetSource
from app.shared.persistence.mixins import utc_now
from app.shared.timezones import local_today, user_zone
from app.workout.models import Exercise, WorkoutPlanEntry, WorkoutPlanExercise, WorkoutScheduleDay

DEMO_USER_ID = "USR-DEMO"
DEMO_USER_EMAIL = "alex.tan@example.com"
DEMO_USER_PASSWORD = "macrorep-demo"


def _demo_today() -> date:
    """Today in the demo profile's zone (the default), which is what the API calls "today" for it."""

    return local_today(user_zone(None))


async def _is_empty(session: AsyncSession, model: type[object]) -> bool:
    result = await session.scalar(select(func.count()).select_from(model))
    return result == 0


async def seed_demo_data() -> None:
    async with get_session_factory()() as session:
        if await _is_empty(session, User):
            session.add(
                User(
                    id=DEMO_USER_ID,
                    name="Alex Tan",
                    email=DEMO_USER_EMAIL,
                    password_hash=hash_password(DEMO_USER_PASSWORD),
                    status=UserStatus.ACTIVE,
                )
            )
            await session.flush()

        if await _is_empty(session, Profile):
            session.add(
                Profile(
                    user_id=DEMO_USER_ID,
                    name="Alex Tan",
                    height_cm=175,
                    goal=Goal.LOSE,
                    weekly_rate_kg=-0.5,
                    training_days_per_week=3,
                    experience_level=ExperienceLevel.INTERMEDIATE,
                    equipment=["barbell", "dumbbell", "bodyweight"],
                    onboarded_utc=utc_now(),
                    date_of_birth=date(1998, 6, 15),
                    sex=Sex.MALE,
                    activity_level=ActivityLevel.MODERATE,
                )
            )
            await session.flush()

        if await _is_empty(session, NutritionTarget):
            session.add(
                NutritionTarget(
                    owner_id=DEMO_USER_ID,
                    version=1,
                    effective_date=_demo_today(),
                    calories=2350,
                    protein_g=165,
                    carbs_g=250,
                    fat_g=70,
                    source=TargetSource.INITIAL,
                )
            )

        if await _is_empty(session, Food):
            session.add_all(
                [
                    Food(
                        id="food-chicken-breast",
                        name="Chicken breast, grilled",
                        serving_size=100,
                        serving_unit="g",
                        serving_weight_g=100,
                        calories=165,
                        protein=31,
                        carbs=0,
                        fat=3.6,
                    ),
                    Food(
                        id="food-white-rice",
                        name="White rice, cooked",
                        serving_size=1,
                        serving_unit="bowl",
                        serving_weight_g=150,
                        calories=195,
                        protein=4,
                        carbs=42,
                        fat=0.4,
                    ),
                    Food(
                        id="food-egg",
                        name="Egg, whole",
                        serving_size=1,
                        serving_unit="piece",
                        serving_weight_g=50,
                        calories=78,
                        protein=6.3,
                        carbs=0.6,
                        fat=5.3,
                    ),
                ]
            )

        exercises = {
            "exercise-bench-press": Exercise(
                id="exercise-bench-press",
                name="Barbell Bench Press",
                equipment="barbell",
                muscles=["chest", "triceps", "shoulders"],
            ),
            "exercise-squat": Exercise(
                id="exercise-squat",
                name="Barbell Back Squat",
                equipment="barbell",
                muscles=["quads", "glutes"],
            ),
            "exercise-deadlift": Exercise(
                id="exercise-deadlift",
                name="Barbell Deadlift",
                equipment="barbell",
                muscles=["back", "hamstrings", "glutes"],
            ),
        }
        if await _is_empty(session, Exercise):
            session.add_all(exercises.values())
            await session.flush()

        if await _is_empty(session, WorkoutPlanEntry):
            today_entry = WorkoutPlanEntry(
                owner_id=DEMO_USER_ID,
                name="Push day",
                week_label="Week 1",
                estimated_minutes=50,
            )
            session.add(today_entry)
            await session.flush()
            session.add(
                WorkoutScheduleDay(
                    owner_id=DEMO_USER_ID, day_of_week=_demo_today().weekday(), routine_id=today_entry.id
                )
            )
            session.add(
                WorkoutPlanExercise(
                    plan_entry_id=today_entry.id,
                    exercise_id="exercise-bench-press",
                    position=0,
                    rest_seconds=120,
                    planned_sets=[
                        {"kind": "warmup", "target_weight_kg": 40, "target_reps": 10},
                        {"kind": "working", "target_weight_kg": 60, "target_reps": 8},
                        {"kind": "working", "target_weight_kg": 60, "target_reps": 8},
                    ],
                )
            )

        if await _is_empty(session, CheckIn):
            # A week that's a little off the goal rate, so the demo check-in has a proposal to review.
            snapshot: dict[str, object] = {
                "avg_calories": 2410,
                "target_calories": 2350,
                "target_version": None,
                "adherence_percent": 85,
                "complete_days": 6,
                "partial_days": 0,
                "missing_days": 0,
                "target_gap_kcal": 360,
                "workouts_done": 3,
                "workouts_planned": 3,
                "completion_percent": 100.0,
                "avg_rpe": 8.0,
                "weight_change_kg": -0.3,
                "goal_rate_kg_per_week": -0.5,
                "goal": "lose",
                "routines": [],
                "exercise_trends": {},
                "equipment": [],
            }
            draft = await run_agents(snapshot, FakeCoachModel())
            today = _demo_today()
            check_in = CheckIn(
                owner_id=DEMO_USER_ID,
                week_label="Week 1",
                range_label=f"{(today - timedelta(days=6)).isoformat()} – {today.isoformat()}",
                summary=draft.summary,
                stats=draft.stats,
                pipeline=draft.pipeline,
                suggested_questions=draft.suggested_questions,
                input_snapshot=snapshot,
            )
            session.add(check_in)
            await session.flush()
            session.add_all(Proposal.from_draft(check_in.id, proposal) for proposal in draft.proposals)

        await session.commit()
