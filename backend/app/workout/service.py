"""Exercise catalog, routines and the weekly schedule, and session business rules."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.training import best_estimated_one_rep_max, is_personal_record, volume_kg
from app.identity.dependencies import ActorContext
from app.profile.repository import ProfileRepository
from app.shared.timezones import local_today, user_zone
from app.shared.validation import MAX_ROUTINES_PER_USER

from .models import Exercise, SetKind, WorkoutPlanEntry, WorkoutPlanExercise, WorkoutSession, WorkoutSetLog
from .repository import ExerciseRepository, WorkoutPlanRepository, WorkoutSessionRepository
from .schemas import (
    AssignDayInput,
    CreateExerciseInput,
    ExerciseRead,
    FinishWorkoutExercise,
    FinishWorkoutInput,
    HistoryExercise,
    HistorySet,
    LastSession,
    PlannedExercise,
    PlannedSet,
    PlannedWorkout,
    PreviousSet,
    RoutineRead,
    SaveRoutineInput,
    UpdateWorkoutInput,
    WeekPlanDay,
    WorkoutDetail,
    WorkoutHistoryItem,
    WorkoutSummary,
)


def _to_exercise_read(exercise: Exercise, last_session: LastSession | None) -> ExerciseRead:
    return ExerciseRead(
        id=exercise.id,
        name=exercise.name,
        equipment=exercise.equipment,
        muscles=list(exercise.muscles),
        source=exercise.source,
        last_session=last_session,
    )


def _history_item(workout_session: WorkoutSession, sets: list[WorkoutSetLog]) -> WorkoutHistoryItem:
    """Totals follow ``finish_session``: every set is completed, every set but a warm-up adds volume."""

    started_at, finished_at = _as_utc(workout_session.started_at), _as_utc(workout_session.finished_at)
    return WorkoutHistoryItem(
        id=workout_session.id,
        name=workout_session.name,
        started_at=started_at,
        duration_seconds=max(int((finished_at - started_at).total_seconds()), 0),
        exercise_count=len({(s.exercise_position, s.exercise_name) for s in sets}),
        sets_completed=len(sets),
        volume_kg=round(volume_kg((float(s.weight_kg), s.reps) for s in sets if s.kind != SetKind.WARMUP), 1),
    )


def _planning_kind(kind: SetKind) -> SetKind:
    """Warm-up or working: failure and drop sets are working sets that went further."""

    return SetKind.WARMUP if kind == SetKind.WARMUP else SetKind.WORKING


def _build_set_logs(
    session_id: str, owner_id: str, exercises: list[FinishWorkoutExercise]
) -> list[WorkoutSetLog]:
    return [
        WorkoutSetLog(
            session_id=session_id,
            owner_id=owner_id,
            exercise_id=exercise_entry.exercise_id,
            exercise_name=exercise_entry.name,
            kind=logged_set.kind,
            weight_kg=logged_set.weight_kg,
            reps=logged_set.reps,
            rpe=logged_set.rpe,
            position=index,
            exercise_position=exercise_index,
        )
        for exercise_index, exercise_entry in enumerate(exercises)
        for index, logged_set in enumerate(exercise_entry.sets)
    ]


def _as_utc(moment: datetime) -> datetime:
    # SQLite hands back naive datetimes; everything is stored in UTC.
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _history_exercises(sets: list[WorkoutSetLog]) -> list[HistoryExercise]:
    """Exercises in the order they were done; sets logged before the order was stored sort last, by name."""

    grouped: dict[tuple[int | None, str], list[WorkoutSetLog]] = {}
    for logged in sets:
        grouped.setdefault((logged.exercise_position, logged.exercise_name), []).append(logged)
    ordered = sorted(grouped, key=lambda key: (key[0] is None, key[0] or 0, key[1]))
    return [
        HistoryExercise(
            exercise_id=grouped[(position, name)][0].exercise_id,
            name=name,
            sets=[
                HistorySet(
                    kind=s.kind,
                    weight_kg=float(s.weight_kg),
                    reps=s.reps,
                    rpe=None if s.rpe is None else float(s.rpe),
                )
                for s in grouped[(position, name)]
            ],
        )
        for position, name in ordered
    ]


class WorkoutService:
    def __init__(
        self,
        session: AsyncSession,
        exercises: ExerciseRepository,
        plans: WorkoutPlanRepository,
        sessions: WorkoutSessionRepository,
        profiles: ProfileRepository,
    ) -> None:
        self.session = session
        self.exercises = exercises
        self.plans = plans
        self.sessions = sessions
        self.profiles = profiles

    async def _zone(self, actor: ActorContext) -> ZoneInfo:
        profile = await self.profiles.get(actor.actor_id)
        return user_zone(profile.timezone if profile else None)

    async def _last_sessions(
        self, actor: ActorContext, exercise_ids: list[str]
    ) -> dict[str, tuple[str, list[WorkoutSetLog]]]:
        return await self.exercises.last_session_sets_bulk(
            actor.actor_id, exercise_ids, await self._zone(actor)
        )

    async def search_exercises(
        self, actor: ActorContext, query: str, muscle: str | None, equipment: str | None, limit: int
    ) -> list[ExerciseRead]:
        rows = await self.exercises.search(actor.actor_id, query, equipment, limit)
        if muscle:
            rows = [row for row in rows if muscle in row.muscles]
        rows = rows[:limit]

        last_sessions = await self._last_sessions(actor, [row.id for row in rows])
        results = []
        for row in rows:
            found = last_sessions.get(row.id)
            last_session = (
                LastSession(
                    date=found[0],
                    sets=[
                        PreviousSet(
                            weight_kg=float(s.weight_kg),
                            reps=s.reps,
                            rpe=float(s.rpe) if s.rpe is not None else None,
                        )
                        for s in found[1]
                    ],
                )
                if found is not None
                else None
            )
            results.append(_to_exercise_read(row, last_session))
        return results

    async def create_exercise(self, payload: CreateExerciseInput, actor: ActorContext) -> ExerciseRead:
        exercise = Exercise(
            owner_id=actor.actor_id, name=payload.name, equipment=payload.equipment, muscles=payload.muscles
        )
        await self.exercises.add(exercise)
        await self.session.commit()
        await self.session.refresh(exercise)
        return _to_exercise_read(exercise, None)

    async def get_today(self, actor: ActorContext) -> PlannedWorkout | None:
        day_of_week = local_today(await self._zone(actor)).weekday()
        plan_entry = await self.plans.get_for_day(actor.actor_id, day_of_week)
        if plan_entry is None:
            return None
        return await self._build_planned_workout(plan_entry, actor)

    async def _planned_workouts(
        self, actor: ActorContext, entries: list[WorkoutPlanEntry]
    ) -> dict[str, PlannedWorkout]:
        """Several routines assembled together, in a handful of queries instead of a few per routine."""

        plan_exercises_by_entry = await self.plans.list_exercises_for_entries([entry.id for entry in entries])
        all_exercise_ids = [pe.exercise_id for pes in plan_exercises_by_entry.values() for pe in pes]
        exercises_by_id = await self.exercises.get_many(all_exercise_ids)
        last_sessions = await self._last_sessions(actor, all_exercise_ids)
        return {
            entry.id: self._assemble_planned_workout(
                entry, plan_exercises_by_entry[entry.id], exercises_by_id, last_sessions
            )
            for entry in entries
        }

    async def get_week_plan(self, actor: ActorContext) -> list[WeekPlanDay]:
        schedule = {row.day_of_week: row.routine_id for row in await self.plans.list_schedule(actor.actor_id)}
        entries = [
            entry
            for entry in await self.plans.list_for_owner(actor.actor_id)
            if entry.id in schedule.values()
        ]
        planned = await self._planned_workouts(actor, entries)
        return [
            WeekPlanDay(day_of_week=day, plan=planned.get(schedule[day]) if day in schedule else None)
            for day in range(7)
        ]

    async def list_routines(self, actor: ActorContext) -> list[RoutineRead]:
        entries = await self.plans.list_for_owner(actor.actor_id)
        planned = await self._planned_workouts(actor, entries)
        days_by_routine: dict[str, list[int]] = {}
        for row in await self.plans.list_schedule(actor.actor_id):
            days_by_routine.setdefault(row.routine_id, []).append(row.day_of_week)
        return [
            RoutineRead(
                **planned[entry.id].model_dump(), scheduled_days=sorted(days_by_routine.get(entry.id, []))
            )
            for entry in entries
        ]

    async def _verify_exercises_owned(
        self, actor: ActorContext, exercise_ids: list[str]
    ) -> dict[str, Exercise]:
        """Fetch exercises by id, raising 404 unless each is global or owned by actor."""

        exercises_by_id = await self.exercises.get_many(exercise_ids)
        for exercise_id in exercise_ids:
            exercise = exercises_by_id.get(exercise_id)
            if exercise is None or (exercise.owner_id is not None and exercise.owner_id != actor.actor_id):
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Exercise {exercise_id} not found")
        return exercises_by_id

    async def _owned_routine(self, actor: ActorContext, routine_id: str) -> WorkoutPlanEntry:
        entry = await self.plans.get(routine_id)
        if entry is None or entry.owner_id != actor.actor_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Routine not found")
        return entry

    async def _save_routine_exercises(
        self, entry: WorkoutPlanEntry, payload: SaveRoutineInput
    ) -> list[WorkoutPlanExercise]:
        new_exercises = [
            WorkoutPlanExercise(
                plan_entry_id=entry.id,
                exercise_id=plan_exercise.exercise_id,
                position=index,
                rest_seconds=plan_exercise.rest_seconds,
                planned_sets=[
                    {
                        "kind": plan_set.kind.value,
                        "target_weight_kg": plan_set.target_weight_kg,
                        "target_reps": plan_set.target_reps,
                    }
                    for plan_set in plan_exercise.sets
                ],
            )
            for index, plan_exercise in enumerate(payload.exercises)
        ]
        await self.plans.replace_exercises(entry.id, new_exercises)
        return new_exercises

    async def _routine_read(self, actor: ActorContext, entry: WorkoutPlanEntry) -> RoutineRead:
        planned = await self._build_planned_workout(entry, actor)
        days = [
            row.day_of_week
            for row in await self.plans.list_schedule(actor.actor_id)
            if row.routine_id == entry.id
        ]
        return RoutineRead(**planned.model_dump(), scheduled_days=sorted(days))

    async def create_routine(self, actor: ActorContext, payload: SaveRoutineInput) -> RoutineRead:
        await self._verify_exercises_owned(actor, [e.exercise_id for e in payload.exercises])
        if await self.plans.count_for_owner(actor.actor_id) >= MAX_ROUTINES_PER_USER:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"You can keep up to {MAX_ROUTINES_PER_USER} routines. Delete one to add another.",
            )
        entry = WorkoutPlanEntry(
            owner_id=actor.actor_id,
            name=payload.name,
            week_label=payload.week_label,
            estimated_minutes=payload.estimated_minutes,
        )
        await self.plans.add(entry)
        await self._save_routine_exercises(entry, payload)
        await self.session.commit()
        return await self._routine_read(actor, entry)

    async def update_routine(
        self, actor: ActorContext, routine_id: str, payload: SaveRoutineInput
    ) -> RoutineRead:
        entry = await self._owned_routine(actor, routine_id)
        await self._verify_exercises_owned(actor, [e.exercise_id for e in payload.exercises])
        entry.name = payload.name
        entry.week_label = payload.week_label
        entry.estimated_minutes = payload.estimated_minutes
        entry.touch()
        await self._save_routine_exercises(entry, payload)
        await self.session.commit()
        return await self._routine_read(actor, entry)

    async def delete_routine(self, actor: ActorContext, routine_id: str) -> None:
        """Delete the routine and take it off the schedule; workouts already logged from it stay."""

        entry = await self._owned_routine(actor, routine_id)
        await self.plans.delete(entry)
        await self.session.commit()

    async def assign_day(self, actor: ActorContext, day_of_week: int, payload: AssignDayInput) -> WeekPlanDay:
        entry = await self._owned_routine(actor, payload.routine_id)
        try:
            await self.plans.set_day(actor.actor_id, day_of_week, entry.id)
            await self.session.commit()
        except IntegrityError:
            # Lost a race: a concurrent save for this same day (e.g. a double-submit) hit
            # the unique (owner_id, day_of_week) index, or the routine was deleted meanwhile.
            await self.session.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT, "This day was just changed elsewhere, please retry"
            ) from None
        return WeekPlanDay(day_of_week=day_of_week, plan=await self._build_planned_workout(entry, actor))

    async def clear_day(self, actor: ActorContext, day_of_week: int) -> None:
        await self.plans.clear_day(actor.actor_id, day_of_week)
        await self.session.commit()

    async def _build_planned_workout(
        self, plan_entry: WorkoutPlanEntry, actor: ActorContext
    ) -> PlannedWorkout:
        plan_exercises = await self.plans.list_exercises(plan_entry.id)
        exercise_ids = [plan_exercise.exercise_id for plan_exercise in plan_exercises]
        exercises_by_id = await self.exercises.get_many(exercise_ids)
        last_sessions = await self._last_sessions(actor, exercise_ids)
        return self._assemble_planned_workout(plan_entry, plan_exercises, exercises_by_id, last_sessions)

    def _assemble_planned_workout(
        self,
        plan_entry: WorkoutPlanEntry,
        plan_exercises: list[WorkoutPlanExercise],
        exercises_by_id: dict[str, Exercise],
        last_sessions: dict[str, tuple[str, list[WorkoutSetLog]]],
    ) -> PlannedWorkout:
        """Pure assembly step, split out from :meth:`_build_planned_workout` so
        ``get_week_plan`` can batch the fetches for all 7 days up front and
        call this once per day instead of running the fetches per day too."""

        exercises: list[PlannedExercise] = []
        for plan_exercise in plan_exercises:
            exercise = exercises_by_id.get(plan_exercise.exercise_id)
            if exercise is None:
                continue
            last_session = last_sessions.get(exercise.id)
            previous_sets = last_session[1] if last_session else []
            # Match previous sets to planned sets by kind (warm-up vs. any other set), not
            # raw list position — a past session with a different set layout would otherwise
            # pair a planned warmup with what was actually a working set's numbers.
            previous_by_kind: dict[SetKind, list[WorkoutSetLog]] = {}
            for row in previous_sets:
                previous_by_kind.setdefault(_planning_kind(row.kind), []).append(row)
            next_index_by_kind: dict[SetKind, int] = {}

            sets: list[PlannedSet] = []
            for index, planned in enumerate(plan_exercise.planned_sets):
                kind = cast(SetKind, planned["kind"])
                bucket_kind = _planning_kind(kind)
                bucket = previous_by_kind.get(bucket_kind, [])
                cursor = next_index_by_kind.get(bucket_kind, 0)
                previous_row = bucket[cursor] if cursor < len(bucket) else None
                if previous_row is not None:
                    next_index_by_kind[bucket_kind] = cursor + 1
                sets.append(
                    PlannedSet(
                        id=f"{plan_exercise.id}-{index}",
                        kind=kind,
                        target_weight_kg=planned.get("target_weight_kg"),
                        target_reps=planned.get("target_reps"),
                        previous=(
                            PreviousSet(
                                weight_kg=float(previous_row.weight_kg),
                                reps=previous_row.reps,
                                rpe=float(previous_row.rpe) if previous_row.rpe is not None else None,
                            )
                            if previous_row is not None
                            else None
                        ),
                    )
                )
            exercises.append(
                PlannedExercise(
                    id=exercise.id,
                    name=exercise.name,
                    equipment=exercise.equipment,
                    muscles=", ".join(exercise.muscles),
                    rest_seconds=plan_exercise.rest_seconds,
                    sets=sets,
                )
            )
        return PlannedWorkout(
            id=plan_entry.id,
            name=plan_entry.name,
            week_label=plan_entry.week_label,
            estimated_minutes=plan_entry.estimated_minutes,
            exercises=exercises,
        )

    async def finish_session(self, payload: FinishWorkoutInput, actor: ActorContext) -> WorkoutSummary:
        plan_id = payload.plan_id
        if plan_id is not None:
            plan_entry = await self.plans.get(plan_id)
            if plan_entry is not None and plan_entry.owner_id != actor.actor_id:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Workout plan not found")
            if plan_entry is None:
                # The routine was deleted while the workout was in progress: keep the
                # workout, just without the link (as deleting a routine does to past ones).
                plan_id = None

        await self._verify_exercises_owned(actor, [e.exercise_id for e in payload.exercises])

        workout_session = WorkoutSession(
            owner_id=actor.actor_id,
            plan_entry_id=plan_id,
            name=payload.name,
            # Stored as UTC whatever offset the client sent, so every reader can
            # rely on it (SQLite keeps the wall-clock time and drops the offset).
            started_at=payload.started_at.astimezone(UTC),
            finished_at=payload.finished_at.astimezone(UTC),
        )
        await self.sessions.add_session(workout_session)

        set_logs = _build_set_logs(workout_session.id, actor.actor_id, payload.exercises)
        await self.sessions.add_sets(set_logs)

        best_before_by_exercise = await self.sessions.best_e1rms_before(
            actor.actor_id, [e.exercise_id for e in payload.exercises], workout_session.id
        )
        personal_records: list[str] = []
        for exercise_entry in payload.exercises:
            best_new = best_estimated_one_rep_max(
                (s.weight_kg, s.reps) for s in exercise_entry.sets if s.kind != SetKind.WARMUP
            )
            if best_new is not None and is_personal_record(
                best_new, best_before_by_exercise.get(exercise_entry.exercise_id)
            ):
                personal_records.append(f"{exercise_entry.name} — new estimated 1RM {round(best_new, 1)} kg")

        session_volume_kg = volume_kg(
            (s.weight_kg, s.reps) for e in payload.exercises for s in e.sets if s.kind != SetKind.WARMUP
        )
        sets_completed = sum(len(e.sets) for e in payload.exercises)
        duration_seconds = int((payload.finished_at - payload.started_at).total_seconds())

        await self.session.commit()
        return WorkoutSummary(
            id=workout_session.id,
            name=workout_session.name,
            duration_seconds=max(duration_seconds, 0),
            sets_completed=sets_completed,
            volume_kg=round(session_volume_kg, 1),
            personal_records=personal_records,
        )

    async def list_history(self, actor: ActorContext, limit: int, offset: int) -> list[WorkoutHistoryItem]:
        sessions = await self.sessions.list_sessions(actor.actor_id, limit, offset)
        sets = await self.sessions.list_sets(actor.actor_id, [s.id for s in sessions])
        sets_by_session: dict[str, list[WorkoutSetLog]] = {}
        for logged in sets:
            sets_by_session.setdefault(logged.session_id, []).append(logged)
        return [_history_item(s, sets_by_session.get(s.id, [])) for s in sessions]

    async def get_history_detail(self, actor: ActorContext, session_id: str) -> WorkoutDetail:
        workout_session = await self.sessions.get_session(actor.actor_id, session_id)
        if workout_session is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Workout not found")
        sets = await self.sessions.list_sets(actor.actor_id, [workout_session.id])
        return WorkoutDetail(
            **_history_item(workout_session, sets).model_dump(), exercises=_history_exercises(sets)
        )

    async def update_session(
        self, actor: ActorContext, session_id: str, payload: UpdateWorkoutInput
    ) -> WorkoutDetail:
        """Replace a logged workout's name and sets; its start and finish times are kept."""

        workout_session = await self.sessions.get_session(actor.actor_id, session_id)
        if workout_session is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Workout not found")
        await self._verify_exercises_owned(actor, [e.exercise_id for e in payload.exercises])

        workout_session.name = payload.name
        workout_session.touch()
        await self.sessions.delete_sets(actor.actor_id, workout_session.id)
        set_logs = _build_set_logs(workout_session.id, actor.actor_id, payload.exercises)
        await self.sessions.add_sets(set_logs)
        await self.session.commit()
        return await self.get_history_detail(actor, session_id)

    async def delete_session(self, actor: ActorContext, session_id: str) -> None:
        workout_session = await self.sessions.get_session(actor.actor_id, session_id)
        if workout_session is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Workout not found")
        await self.sessions.delete_session(workout_session)
        await self.session.commit()
