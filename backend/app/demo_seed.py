"""Idempotent local demo data used only when ``SEED_DEMO_DATA`` is enabled.

Seeds one user (id ``USR-DEMO``) that local development can sign in as, either
by posting the email/password below to `/api/v1/auth/login` or by sending
`X-Preview-Actor-Id: USR-DEMO` while `PREVIEW_AUTH_ENABLED` is on.

``SEED_DEMO_HISTORY`` adds four weeks of logs on top, enough for Progress to have something
to show and for a real check-in to start. It's dated from the day it's seeded, so reseed on
the day of a demo.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.energy import ActivityLevel, Sex
from app.auth.security import hash_password
from app.body.models import WeighIn
from app.core.database import get_session_factory
from app.food.catalog import ensure_system_foods
from app.food.models import FoodEntry
from app.food.repository import FoodEntryRepository, FoodRepository
from app.food.schemas import CreateFoodEntryInput
from app.food.service import FoodService
from app.identity.dependencies import ActorContext
from app.identity.models import User, UserStatus
from app.profile.models import ExperienceLevel, Goal, NutritionTarget, Profile, TargetSource
from app.profile.repository import ProfileRepository
from app.shared.persistence.mixins import utc_now
from app.shared.timezones import local_today, user_zone
from app.workout.catalog import ensure_system_exercises
from app.workout.models import SetKind, WorkoutPlanEntry, WorkoutPlanExercise, WorkoutScheduleDay
from app.workout.repository import ExerciseRepository, WorkoutPlanRepository, WorkoutSessionRepository
from app.workout.schemas import FinishWorkoutExercise, FinishWorkoutInput, LoggedSet
from app.workout.service import WorkoutService

DEMO_USER_ID = "USR-DEMO"
DEMO_USER_EMAIL = "alex.yau@example.com"
DEMO_USER_PASSWORD = "nailong"

# The presenter's zone: the browser would set it at sign-in anyway, and every date below hangs on it.
DEMO_TIMEZONE = "Asia/Singapore"
HISTORY_DAYS = 28

# A rotating week of eating, close to the 2,350 kcal target: (meal, food id, servings).
MENUS: tuple[tuple[tuple[str, str, float], ...], ...] = (
    (
        ("breakfast", "food-oats", 2),
        ("breakfast", "food-whey-protein", 1),
        ("breakfast", "food-banana", 1),
        ("breakfast", "food-wholemeal-bread", 2),
        ("lunch", "food-chicken-rice", 1),
        ("dinner", "food-white-rice", 2),
        ("dinner", "food-chicken-breast", 2),
        ("dinner", "food-broccoli", 1),
        ("snacks", "food-greek-yogurt-nonfat", 1),
        ("snacks", "food-apple", 1),
        ("snacks", "food-low-fat-milk", 1),
    ),
    (
        ("breakfast", "food-egg", 3),
        ("breakfast", "food-wholemeal-bread", 2),
        ("lunch", "food-economy-rice", 1),
        ("dinner", "food-sliced-fish-soup", 1),
        ("dinner", "food-salmon", 1.5),
        ("dinner", "food-brown-rice", 1),
        ("snacks", "food-whey-protein", 2),
        ("snacks", "food-banana", 1),
        ("snacks", "food-apple", 1),
        ("snacks", "food-low-fat-milk", 1),
    ),
    (
        ("breakfast", "food-oats", 2),
        ("breakfast", "food-greek-yogurt-nonfat", 1),
        ("breakfast", "food-wholemeal-bread", 1),
        ("lunch", "food-yong-tau-foo", 1),
        ("dinner", "food-brown-rice", 3),
        ("dinner", "food-beef-sirloin", 2),
        ("dinner", "food-broccoli", 1),
        ("snacks", "food-whey-protein", 1),
        ("snacks", "food-apple", 1),
        ("snacks", "food-banana", 1),
        ("snacks", "food-low-fat-milk", 1),
    ),
    (
        ("breakfast", "food-roti-prata", 2),
        ("breakfast", "food-egg", 1),
        ("lunch", "food-nasi-lemak", 1),
        ("dinner", "food-bak-chor-mee", 1),
        ("dinner", "food-chicken-breast", 1),
        ("dinner", "food-white-rice", 1),
        ("snacks", "food-whey-protein", 2),
        ("snacks", "food-greek-yogurt-nonfat", 1),
        ("snacks", "food-apple", 1),
        ("snacks", "food-low-fat-milk", 1),
    ),
)

# Unlogged, so the record looks like a person's: days before the week a check-in reviews.
FOOD_DAYS_MISSED = (12, 20)
WORKOUTS_MISSED = (17,)

# One exercise of a routine: its weight and RPE over the four weeks, oldest first.
Lift = tuple[str, str, int, tuple[float, float, float, float], tuple[float, float, float, float]]

# Routines by how many days after today they fall, so one is always due on the day of the demo.
# Weight is slower than the goal, the pulldown is getting easy, and the squat is getting hard,
# which gives each agent something to say.
PUSH_DAY: tuple[Lift, ...] = (
    ("exercise-bench-press", "Barbell Bench Press", 8, (55, 57.5, 60, 60), (8.5, 8.5, 8, 7.5)),
    ("exercise-overhead-press", "Barbell Overhead Press", 8, (35, 35, 37.5, 37.5), (8, 8, 8.5, 8)),
    ("exercise-db-lateral-raise", "Dumbbell Lateral Raise", 12, (8, 8, 10, 10), (8, 7.5, 8.5, 8)),
    ("exercise-triceps-pushdown", "Cable Triceps Pushdown", 12, (20, 22.5, 22.5, 25), (8, 8, 7.5, 8)),
)
PULL_DAY: tuple[Lift, ...] = (
    ("exercise-lat-pulldown", "Lat Pulldown", 10, (50, 52.5, 55, 55), (8.5, 8, 7.5, 6.5)),
    ("exercise-seated-cable-row", "Seated Cable Row", 10, (50, 50, 52.5, 55), (8, 7.5, 8, 7.5)),
    ("exercise-db-curl", "Dumbbell Curl", 12, (10, 10, 12, 12), (8, 7.5, 8.5, 8)),
)
LEG_DAY: tuple[Lift, ...] = (
    ("exercise-squat", "Barbell Back Squat", 6, (80, 80, 80, 80), (8, 8.5, 9, 9.5)),
    ("exercise-rdl", "Barbell Romanian Deadlift", 8, (70, 70, 72.5, 75), (7.5, 7.5, 8, 8)),
    ("exercise-lying-leg-curl", "Lying Leg Curl", 12, (35, 35, 37.5, 37.5), (8, 7.5, 8, 8)),
    ("exercise-standing-calf-raise", "Standing Calf Raise", 12, (50, 50, 55, 55), (8, 7.5, 8, 7.5)),
)
ROUTINES: dict[int, tuple[str, tuple[Lift, ...]]] = {
    0: ("Push day", PUSH_DAY),
    2: ("Pull day", PULL_DAY),
    4: ("Leg day", LEG_DAY),
}


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
                    name="Alex Yau",
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
                    name="Alex Yau",
                    height_cm=175,
                    goal=Goal.LOSE,
                    weekly_rate_kg=-0.5,
                    experience_level=ExperienceLevel.INTERMEDIATE,
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

        await ensure_system_exercises(session)

        if await _is_empty(session, WorkoutPlanEntry):
            today_entry = WorkoutPlanEntry(owner_id=DEMO_USER_ID, name="Push day")
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

        await session.commit()


def _warmup_kg(working_kg: float) -> float:
    """Two thirds of the working weight, to the nearest 2.5 kg plate jump."""

    return round(working_kg * 2 / 3 / 2.5) * 2.5


def _planned_sets(lift: Lift) -> list[dict[str, object]]:
    _, _, reps, weights, _ = lift
    return [
        {"kind": "warmup", "target_weight_kg": _warmup_kg(weights[-1]), "target_reps": reps},
        {"kind": "working", "target_weight_kg": weights[-1], "target_reps": reps},
        {"kind": "working", "target_weight_kg": weights[-1], "target_reps": reps},
    ]


def _logged_lift(lift: Lift, week: int) -> FinishWorkoutExercise:
    exercise_id, name, reps, weights, rpes = lift
    working = LoggedSet(kind=SetKind.WORKING, weight_kg=weights[week], reps=reps, rpe=rpes[week])
    warmup = LoggedSet(kind=SetKind.WARMUP, weight_kg=_warmup_kg(weights[week]), reps=reps)
    return FinishWorkoutExercise(exercise_id=exercise_id, name=name, sets=[warmup, working, working])


def _trend_weight(days_ago: int) -> float:
    """About 0.2 kg a week off, slower than the 0.5 kg goal, with a day-to-day wobble."""

    wobble = (0.2, -0.1, 0.1, -0.2, 0.0)[days_ago % 5]
    return round(78.0 + 0.03 * days_ago + wobble, 2)


async def _seed_plan(session: AsyncSession, today: date) -> dict[str, str]:
    """Build out the routines and schedule them from today. Returns routine ids by name."""

    push_day = await session.scalar(select(WorkoutPlanEntry).where(WorkoutPlanEntry.owner_id == DEMO_USER_ID))
    assert push_day is not None  # seed_demo_data made it
    await session.execute(
        update(WorkoutScheduleDay)
        .where(WorkoutScheduleDay.routine_id == push_day.id)
        .values(day_of_week=today.weekday())
    )
    routine_ids = {push_day.name: push_day.id}
    for offset, (name, lifts) in ROUTINES.items():
        if name == push_day.name:
            routine = push_day
        else:
            routine = WorkoutPlanEntry(owner_id=DEMO_USER_ID, name=name)
            session.add(routine)
            await session.flush()
            routine_ids[name] = routine.id
            day = (today + timedelta(days=offset)).weekday()
            session.add(WorkoutScheduleDay(owner_id=DEMO_USER_ID, day_of_week=day, routine_id=routine.id))
        await session.execute(
            delete(WorkoutPlanExercise).where(WorkoutPlanExercise.plan_entry_id == routine.id)
        )
        session.add_all(
            WorkoutPlanExercise(
                plan_entry_id=routine.id,
                exercise_id=lift[0],
                position=position,
                rest_seconds=120 if position == 0 else 90,
                planned_sets=_planned_sets(lift),
            )
            for position, lift in enumerate(lifts)
        )
    return routine_ids


async def _seed_food(session: AsyncSession, actor: ActorContext, today: date) -> None:
    """Every day but the missed ones, and only today's breakfast, leaving the day to log live."""

    food = FoodService(session, FoodRepository(session), FoodEntryRepository(session))
    for days_ago in range(HISTORY_DAYS):
        if days_ago in FOOD_DAYS_MISSED:
            continue
        for meal, food_id, servings in MENUS[days_ago % len(MENUS)]:
            if days_ago > 0 or meal == "breakfast":
                entry = CreateFoodEntryInput(
                    date=today - timedelta(days=days_ago), meal=meal, food_id=food_id, quantity=servings
                )
                await food.add_entry(entry, actor)


async def _seed_workouts(
    session: AsyncSession, actor: ActorContext, routine_ids: dict[str, str], today: date, zone: ZoneInfo
) -> None:
    """The routine due on each past day, oldest first. Today's is left to log live."""

    workouts = WorkoutService(
        session,
        ExerciseRepository(session),
        WorkoutPlanRepository(session),
        WorkoutSessionRepository(session),
        ProfileRepository(session),
    )
    for days_ago in range(HISTORY_DAYS - 1, 0, -1):
        due = ROUTINES.get(-days_ago % 7)
        if due is None or days_ago in WORKOUTS_MISSED:
            continue
        name, lifts = due
        week = 3 - (days_ago - 1) // 7
        started = datetime.combine(today - timedelta(days=days_ago), time(18, 30), tzinfo=zone)
        await workouts.finish_session(
            FinishWorkoutInput(
                plan_id=routine_ids[name],
                name=name,
                started_at=started,
                finished_at=started + timedelta(minutes=55),
                exercises=[_logged_lift(lift, week) for lift in lifts],
            ),
            actor,
        )


async def seed_demo_history() -> None:
    """Four weeks of the demo user's logs, left off in the tests, which start from an empty account."""

    async with get_session_factory()() as session:
        if not await _is_empty(session, FoodEntry):
            return

        zone = ZoneInfo(DEMO_TIMEZONE)
        today = local_today(zone)
        actor = ActorContext(actor_id=DEMO_USER_ID, display_name="Alex Yau")

        profile = await session.get(Profile, DEMO_USER_ID)
        assert profile is not None  # seed_demo_data made it
        profile.timezone = DEMO_TIMEZONE
        await session.execute(
            update(NutritionTarget)
            .where(NutritionTarget.owner_id == DEMO_USER_ID)
            .values(effective_date=today - timedelta(days=HISTORY_DAYS))
        )
        await ensure_system_foods(session)
        routine_ids = await _seed_plan(session, today)
        session.add_all(
            WeighIn(
                owner_id=DEMO_USER_ID,
                log_date=today - timedelta(days=days_ago),
                weight_kg=_trend_weight(days_ago),
            )
            for days_ago in range(1, HISTORY_DAYS)
            if days_ago % 7 != 4  # most mornings, not every one
        )
        await _seed_food(session, actor, today)
        await _seed_workouts(session, actor, routine_ids, today, zone)
        await session.commit()
