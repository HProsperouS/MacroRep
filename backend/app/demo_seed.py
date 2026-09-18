"""Idempotent local demo data used only when ``SEED_DEMO_DATA`` is enabled.

Seeds one user (id ``USR-DEMO``) that local development can sign in as, either
by posting the email/password below to `/api/auth/login` or by sending
`X-Preview-Actor-Id: USR-DEMO` while `PREVIEW_AUTH_ENABLED` is on.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.coach import pipeline
from app.coach.models import CheckIn, Proposal
from app.core.database import get_session_factory
from app.food.models import Food
from app.identity.models import User, UserStatus
from app.profile.models import Goal, Profile
from app.workout.models import Exercise, WorkoutPlanEntry, WorkoutPlanExercise

DEMO_USER_ID = "USR-DEMO"
DEMO_USER_EMAIL = "alex.tan@example.com"
DEMO_USER_PASSWORD = "macrorep-demo"


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
                    target_calories=2350,
                    target_protein_g=165,
                    target_carbs_g=250,
                    target_fat_g=70,
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
                day_of_week=date.today().weekday(),
                name="Push day",
                week_label="Week 1",
                estimated_minutes=50,
            )
            session.add(today_entry)
            await session.flush()
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
            draft = pipeline.draft_check_in(
                week_label="Week 1",
                avg_calories=2410,
                target_calories=2350,
                adherence_percent=85,
                workouts_done=3,
                workouts_planned=3,
                weight_change_kg=-0.3,
                goal_rate_kg_per_week=-0.5,
            )
            check_in = CheckIn(
                owner_id=DEMO_USER_ID,
                week_label="Week 1",
                range_label=f"{(date.today() - timedelta(days=6)).isoformat()} – {date.today().isoformat()}",
                summary=draft.summary,
                stats=draft.stats,
                pipeline=draft.pipeline,
                suggested_questions=draft.suggested_questions,
            )
            session.add(check_in)
            await session.flush()
            session.add_all(
                Proposal(
                    check_in_id=check_in.id,
                    kind=proposal.kind,
                    headline=proposal.headline,
                    changes=[change.__dict__ for change in proposal.changes],
                    evidence=proposal.evidence,
                    reviewer_note=proposal.reviewer_note,
                )
                for proposal in draft.proposals
            )

        await session.commit()
