"""Exercise catalog, routines and the weekly schedule, and session business rules."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date
from typing import cast
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.training import (
    RPE_ROOM_TO_PROGRESS,
    best_estimated_one_rep_max,
    effective_load_kg,
    estimated_minutes,
    is_personal_record,
    is_rep_based,
    next_session_target,
    volume_kg,
)
from app.identity.dependencies import ActorContext
from app.profile.repository import ProfileRepository
from app.profile.service import zone_of
from app.shared.exceptions import Conflict, Invalid, NotFound
from app.shared.timezones import local_date, local_today, utc_bounds
from app.shared.validation import MAX_CUSTOM_EXERCISES_PER_USER, MAX_ROUTINES_PER_USER

from .models import Exercise, SetKind, WorkoutPlanEntry, WorkoutPlanExercise, WorkoutSession, WorkoutSetLog
from .repository import ExerciseRepository, WorkoutPlanRepository, WorkoutSessionRepository
from .schemas import (
    AssignDayInput,
    CreateExerciseInput,
    ExerciseNoteRead,
    ExerciseRead,
    FinishWorkoutExercise,
    FinishWorkoutInput,
    HistoryExercise,
    HistorySet,
    LastSession,
    NextTargetRead,
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
from .targets import suggested_loads


def _to_exercise_read(
    exercise: Exercise, last_session: LastSession | None, user_note: str | None = None
) -> ExerciseRead:
    return ExerciseRead(
        id=exercise.id,
        name=exercise.name,
        equipment=exercise.equipment,
        muscles=list(exercise.muscles),
        source=exercise.source,
        last_session=last_session,
        user_note=user_note,
    )


def _history_item(workout_session: WorkoutSession, sets: list[WorkoutSetLog]) -> WorkoutHistoryItem:
    """Totals follow ``finish_session``: every set is completed, every set but a warm-up adds volume."""

    started_at, finished_at = workout_session.started_at, workout_session.finished_at
    return WorkoutHistoryItem(
        id=workout_session.id,
        name=workout_session.name,
        started_at=started_at,
        duration_seconds=max(int((finished_at - started_at).total_seconds()), 0),
        exercise_count=len({(s.exercise_position, s.exercise_name) for s in sets}),
        sets_completed=len(sets),
        volume_kg=round(volume_kg((float(s.load_kg), s.reps) for s in sets if s.kind != SetKind.WARMUP), 1),
        rep_based_reps=_rep_based_reps((float(s.load_kg), s.kind, s.reps) for s in sets),
        body_weight_kg=_optional_float(workout_session.body_weight_kg),
    )


def _rep_based_reps(sets: Iterable[tuple[float, SetKind, int]]) -> int:
    """Working reps of sets with no load (bands), which kg volume can't count."""

    return sum(reps for load_kg, kind, reps in sets if kind != SetKind.WARMUP and is_rep_based(load_kg))


def _optional_float(value: float | None) -> float | None:
    return None if value is None else float(value)


def _progression_kg(exercise: Exercise | None, typed_kg: float) -> float:
    """The weight progression steps from: what was typed (the added kg on a bodyweight move),
    except a band, whose kg is a guess and progresses by reps."""

    return 0.0 if exercise is not None and exercise.equipment == "band" else float(typed_kg)


def _planning_kind(kind: SetKind) -> SetKind:
    """Warm-up or working: failure and drop sets are working sets that went further."""

    return SetKind.WARMUP if kind == SetKind.WARMUP else SetKind.WORKING


def _build_set_logs(
    workout_session: WorkoutSession,
    exercises: list[FinishWorkoutExercise],
    exercises_by_id: dict[str, Exercise],
) -> list[WorkoutSetLog]:
    """Each set with the load its analytics use, from its exercise's equipment and the
    bodyweight the workout was logged at (see :func:`effective_load_kg`)."""

    body_weight_kg = _optional_float(workout_session.body_weight_kg)

    def equipment(exercise_id: str) -> str | None:
        exercise = exercises_by_id.get(exercise_id)
        return exercise.equipment if exercise else None

    def typed(exercise_id: str, weight_kg: float) -> float:
        # A band has no weight to log (its kg would be a guess), whatever a client sends.
        return 0.0 if equipment(exercise_id) == "band" else weight_kg

    return [
        WorkoutSetLog(
            session_id=workout_session.id,
            owner_id=workout_session.owner_id,
            exercise_id=exercise_entry.exercise_id,
            exercise_name=exercise_entry.name,
            kind=logged_set.kind,
            weight_kg=typed(exercise_entry.exercise_id, logged_set.weight_kg),
            load_kg=effective_load_kg(
                equipment(exercise_entry.exercise_id),
                typed(exercise_entry.exercise_id, logged_set.weight_kg),
                body_weight_kg,
            ),
            reps=logged_set.reps,
            rpe=logged_set.rpe,
            position=index,
            exercise_position=exercise_index,
        )
        for exercise_index, exercise_entry in enumerate(exercises)
        for index, logged_set in enumerate(exercise_entry.sets)
    ]


def _history_exercises(sets: list[WorkoutSetLog], equipment_by_id: dict[str, str]) -> list[HistoryExercise]:
    """Exercises in the order they were done; sets logged before the order was stored sort last, by name."""

    grouped: dict[tuple[int | None, str], list[WorkoutSetLog]] = {}
    for logged in sets:
        grouped.setdefault((logged.exercise_position, logged.exercise_name), []).append(logged)
    ordered = sorted(grouped, key=lambda key: (key[0] is None, key[0] or 0, key[1]))
    return [
        HistoryExercise(
            exercise_id=grouped[(position, name)][0].exercise_id,
            name=name,
            equipment=equipment_by_id.get(grouped[(position, name)][0].exercise_id or ""),
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
        return zone_of(await self.profiles.get(actor.actor_id))

    async def _last_sessions(
        self, actor: ActorContext, exercise_ids: list[str]
    ) -> dict[str, tuple[str, list[WorkoutSetLog]]]:
        return await self.exercises.last_session_sets_bulk(
            actor.actor_id, exercise_ids, await self._zone(actor)
        )

    async def search_exercises(
        self, actor: ActorContext, query: str, muscle: str | None, equipment: str | None, limit: int
    ) -> list[ExerciseRead]:
        rows = await self.exercises.search(actor.actor_id, query, muscle, equipment, limit)

        last_sessions = await self._last_sessions(actor, [row.id for row in rows])
        notes = await self.exercises.notes_bulk(actor.actor_id, [row.id for row in rows])
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
            results.append(_to_exercise_read(row, last_session, notes.get(row.id)))
        return results

    async def create_exercise(self, payload: CreateExerciseInput, actor: ActorContext) -> ExerciseRead:
        if await self.exercises.count_custom(actor.actor_id) >= MAX_CUSTOM_EXERCISES_PER_USER:
            raise Invalid(
                f"You can create up to {MAX_CUSTOM_EXERCISES_PER_USER} exercises of your own.",
            )
        exercise = Exercise(
            owner_id=actor.actor_id, name=payload.name, equipment=payload.equipment, muscles=payload.muscles
        )
        await self.exercises.add(exercise)
        await self.session.commit()
        await self.session.refresh(exercise)
        return _to_exercise_read(exercise, None)

    async def set_exercise_note(self, actor: ActorContext, exercise_id: str, body: str) -> ExerciseNoteRead:
        await self._verify_exercises_owned(actor, [exercise_id])
        await self.exercises.set_note(actor.actor_id, exercise_id, body)
        await self.session.commit()
        return ExerciseNoteRead(exercise_id=exercise_id, body=body)

    async def get_today(self, actor: ActorContext) -> PlannedWorkout | None:
        day_of_week = local_today(await self._zone(actor)).weekday()
        plan_entry = await self.plans.get_for_day(actor.actor_id, day_of_week)
        if plan_entry is None:
            return None
        # Today's session is the one place the last session's result shapes the targets; the
        # routine editor and the week plan show the routine as saved.
        return await self._build_planned_workout(plan_entry, actor, suggest_loads=True)

    async def _planned_workouts(
        self, actor: ActorContext, entries: list[WorkoutPlanEntry]
    ) -> dict[str, PlannedWorkout]:
        """Several routines assembled together, in a handful of queries instead of a few per routine."""

        plan_exercises_by_entry = await self.plans.list_exercises_for_entries([entry.id for entry in entries])
        all_exercise_ids = [pe.exercise_id for pes in plan_exercises_by_entry.values() for pe in pes]
        exercises_by_id = await self.exercises.get_many(all_exercise_ids)
        last_sessions = await self._last_sessions(actor, all_exercise_ids)
        notes = await self.exercises.notes_bulk(actor.actor_id, all_exercise_ids)
        return {
            entry.id: self._assemble_planned_workout(
                entry, plan_exercises_by_entry[entry.id], exercises_by_id, last_sessions, notes
            )
            for entry in entries
        }

    async def get_week_plan(self, actor: ActorContext) -> list[WeekPlanDay]:
        schedule = {row.day_of_week: row.routine_id for row in await self.plans.list_schedule(actor.actor_id)}
        # Only the routines the week uses; the unscheduled ones are the Routine list's.
        planned = await self._planned_workouts(
            actor, list((await self.plans.get_many(list(schedule.values()))).values())
        )
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
                raise NotFound(f"Exercise {exercise_id} not found")
        return exercises_by_id

    async def _owned_routine(self, actor: ActorContext, routine_id: str) -> WorkoutPlanEntry:
        entry = await self.plans.get(routine_id)
        if entry is None or entry.owner_id != actor.actor_id:
            raise NotFound("Routine not found")
        return entry

    async def _owned_session(self, actor: ActorContext, session_id: str) -> WorkoutSession:
        workout_session = await self.sessions.get_session(actor.actor_id, session_id)
        if workout_session is None:
            raise NotFound("Workout not found")
        return workout_session

    async def _save_routine_exercises(
        self, entry: WorkoutPlanEntry, payload: SaveRoutineInput, exercises_by_id: dict[str, Exercise]
    ) -> list[WorkoutPlanExercise]:
        """A band exercise keeps no target weight: it's tracked by reps (its kg would be a guess)."""

        def is_band(exercise_id: str) -> bool:
            exercise = exercises_by_id.get(exercise_id)
            return exercise is not None and exercise.equipment == "band"

        new_exercises = [
            WorkoutPlanExercise(
                plan_entry_id=entry.id,
                exercise_id=plan_exercise.exercise_id,
                position=index,
                rest_seconds=plan_exercise.rest_seconds,
                planned_sets=[
                    {
                        "kind": plan_set.kind.value,
                        "target_weight_kg": None
                        if is_band(plan_exercise.exercise_id)
                        else plan_set.target_weight_kg,
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
        exercises_by_id = await self._verify_exercises_owned(
            actor, [e.exercise_id for e in payload.exercises]
        )
        if await self.plans.count_for_owner(actor.actor_id) >= MAX_ROUTINES_PER_USER:
            raise Invalid(
                f"You can keep up to {MAX_ROUTINES_PER_USER} routines. Delete one to add another.",
            )
        entry = WorkoutPlanEntry(owner_id=actor.actor_id, name=payload.name)
        await self.plans.add(entry)
        await self._save_routine_exercises(entry, payload, exercises_by_id)
        await self.session.commit()
        return await self._routine_read(actor, entry)

    async def update_routine(
        self, actor: ActorContext, routine_id: str, payload: SaveRoutineInput
    ) -> RoutineRead:
        entry = await self._owned_routine(actor, routine_id)
        exercises_by_id = await self._verify_exercises_owned(
            actor, [e.exercise_id for e in payload.exercises]
        )
        entry.name = payload.name
        entry.touch()
        await self._save_routine_exercises(entry, payload, exercises_by_id)
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
            raise Conflict("This day was just changed elsewhere, please retry") from None
        return WeekPlanDay(day_of_week=day_of_week, plan=await self._build_planned_workout(entry, actor))

    async def clear_day(self, actor: ActorContext, day_of_week: int) -> None:
        await self.plans.clear_day(actor.actor_id, day_of_week)
        await self.session.commit()

    async def _build_planned_workout(
        self, plan_entry: WorkoutPlanEntry, actor: ActorContext, *, suggest_loads: bool = False
    ) -> PlannedWorkout:
        plan_exercises = await self.plans.list_exercises(plan_entry.id)
        exercise_ids = [plan_exercise.exercise_id for plan_exercise in plan_exercises]
        exercises_by_id = await self.exercises.get_many(exercise_ids)
        last_sessions = await self._last_sessions(actor, exercise_ids)
        notes = await self.exercises.notes_bulk(actor.actor_id, exercise_ids)
        return self._assemble_planned_workout(
            plan_entry, plan_exercises, exercises_by_id, last_sessions, notes, suggest_loads=suggest_loads
        )

    def _assemble_planned_workout(
        self,
        plan_entry: WorkoutPlanEntry,
        plan_exercises: list[WorkoutPlanExercise],
        exercises_by_id: dict[str, Exercise],
        last_sessions: dict[str, tuple[str, list[WorkoutSetLog]]],
        notes: dict[str, str],
        *,
        suggest_loads: bool = False,
    ) -> PlannedWorkout:
        """Pure assembly step, split out from :meth:`_build_planned_workout` so
        ``get_week_plan`` can batch the fetches for all 7 days up front and
        call this once per day instead of running the fetches per day too.

        With ``suggest_loads``, each exercise's heaviest working target is raised to what its
        last session earned (see :func:`suggested_loads`), with a note saying why."""

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
            planned_sets = plan_exercise.planned_sets
            note: str | None = None
            if suggest_loads:
                planned_sets, raised = suggested_loads(
                    planned_sets,
                    [
                        (
                            _progression_kg(exercise, float(row.weight_kg)),
                            row.reps,
                            float(row.rpe) if row.rpe is not None else None,
                        )
                        for row in previous_sets
                        if row.kind == SetKind.WORKING
                    ],
                )
                if raised is not None:
                    goal = f"{raised.reps} reps" if raised.weight_kg <= 0 else f"{raised.weight_kg:g} kg"
                    note = (
                        f"Up to {goal}: last time every rep came with room to spare "
                        f"(RPE {RPE_ROOM_TO_PROGRESS:g} or less)."
                    )
            previous_by_kind: dict[SetKind, list[WorkoutSetLog]] = {}
            for row in previous_sets:
                previous_by_kind.setdefault(_planning_kind(row.kind), []).append(row)
            next_index_by_kind: dict[SetKind, int] = {}

            sets: list[PlannedSet] = []
            for index, planned in enumerate(planned_sets):
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
                    note=note,
                    user_note=notes.get(exercise.id),
                    sets=sets,
                )
            )
        return PlannedWorkout(
            id=plan_entry.id,
            name=plan_entry.name,
            estimated_minutes=estimated_minutes(
                (len(exercise.sets), exercise.rest_seconds) for exercise in exercises
            ),
            exercises=exercises,
        )

    async def finish_session(self, payload: FinishWorkoutInput, actor: ActorContext) -> WorkoutSummary:
        plan_id = payload.plan_id
        if plan_id is not None:
            plan_entry = await self.plans.get(plan_id)
            if plan_entry is not None and plan_entry.owner_id != actor.actor_id:
                raise NotFound("Workout plan not found")
            if plan_entry is None:
                # The routine was deleted while the workout was in progress: keep the
                # workout, just without the link (as deleting a routine does to past ones).
                plan_id = None

        exercises_by_id = await self._verify_exercises_owned(
            actor, [e.exercise_id for e in payload.exercises]
        )
        started_at = payload.started_at.astimezone(UTC)
        body_weight_kg = await self.sessions.body_weight_on(
            actor.actor_id, local_date(started_at, await self._zone(actor))
        )

        workout_session = WorkoutSession(
            owner_id=actor.actor_id,
            plan_entry_id=plan_id,
            name=payload.name,
            # Stored as UTC whatever offset the client sent.
            started_at=started_at,
            finished_at=payload.finished_at.astimezone(UTC),
            body_weight_kg=body_weight_kg,
        )
        await self.sessions.add_session(workout_session)

        set_logs = _build_set_logs(workout_session, payload.exercises, exercises_by_id)
        await self.sessions.add_sets(set_logs)
        counted = [s for s in set_logs if s.kind != SetKind.WARMUP]
        exercise_ids = [e.exercise_id for e in payload.exercises]

        best_before_by_exercise = await self.sessions.best_e1rms_before(
            actor.actor_id, exercise_ids, workout_session.id
        )
        best_reps_before_by_exercise = await self.sessions.best_reps_before(
            actor.actor_id, exercise_ids, workout_session.id
        )
        personal_records: list[str] = []
        for exercise_index, exercise_entry in enumerate(payload.exercises):
            own = [s for s in counted if s.exercise_position == exercise_index]
            best_new = best_estimated_one_rep_max((float(s.load_kg), s.reps) for s in own)
            if best_new is not None:
                if is_personal_record(best_new, best_before_by_exercise.get(exercise_entry.exercise_id)):
                    personal_records.append(
                        f"{exercise_entry.name} — new estimated 1RM {round(best_new, 1)} kg"
                    )
                continue
            # No load at all (a band): the record is the most reps in one set.
            best_reps = max((s.reps for s in own if is_rep_based(float(s.load_kg))), default=0)
            if best_reps > 0 and best_reps > best_reps_before_by_exercise.get(exercise_entry.exercise_id, 0):
                personal_records.append(f"{exercise_entry.name} — new best {best_reps} reps")

        next_targets = await self._next_targets(plan_id, payload, exercises_by_id)

        session_volume_kg = volume_kg((float(s.load_kg), s.reps) for s in counted)
        sets_completed = sum(len(e.sets) for e in payload.exercises)
        duration_seconds = int((payload.finished_at - payload.started_at).total_seconds())

        await self.session.commit()
        return WorkoutSummary(
            id=workout_session.id,
            name=workout_session.name,
            duration_seconds=max(duration_seconds, 0),
            sets_completed=sets_completed,
            volume_kg=round(session_volume_kg, 1),
            rep_based_reps=_rep_based_reps((float(s.load_kg), s.kind, s.reps) for s in set_logs),
            body_weight_kg=body_weight_kg,
            personal_records=personal_records,
            next_targets=next_targets,
            exercises=_history_exercises(set_logs, {key: e.equipment for key, e in exercises_by_id.items()}),
        )

    async def _next_targets(
        self, plan_id: str | None, payload: FinishWorkoutInput, exercises_by_id: dict[str, Exercise]
    ) -> list[NextTargetRead]:
        """A target for each routine exercise done today, from its sets against the routine's reps.

        Only for a workout started from a routine: without one there are no target reps to
        judge the sets against. A suggestion for next time only; the routine itself is
        changed only by an approved check-in.
        """

        if plan_id is None:
            return []
        target_reps_by_exercise: dict[str, int] = {}
        for plan_exercise in await self.plans.list_exercises(plan_id):
            working_reps = [
                cast(int, planned["target_reps"])
                for planned in plan_exercise.planned_sets
                if planned.get("kind") == SetKind.WORKING.value and planned.get("target_reps") is not None
            ]
            if working_reps:
                target_reps_by_exercise[plan_exercise.exercise_id] = max(working_reps)

        targets: list[NextTargetRead] = []
        for exercise_entry in payload.exercises:
            exercise = exercises_by_id.get(exercise_entry.exercise_id)
            target = next_session_target(
                [
                    (_progression_kg(exercise, s.weight_kg), s.reps, s.rpe)
                    for s in exercise_entry.sets
                    if s.kind == SetKind.WORKING
                ],
                target_reps_by_exercise.get(exercise_entry.exercise_id),
            )
            if target is not None:
                targets.append(
                    NextTargetRead(
                        exercise=exercise_entry.name,
                        weight_kg=target.weight_kg,
                        reps=target.reps,
                        increase=target.increase,
                    )
                )
        return targets

    async def list_history(
        self,
        actor: ActorContext,
        limit: int,
        offset: int,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[WorkoutHistoryItem]:
        """Logged workouts newest first, optionally only those started on the user's local days
        ``date_from`` to ``date_to`` (inclusive; either end may be open)."""

        since = until = None
        if date_from is not None or date_to is not None:
            zone = await self._zone(actor)
            if date_from is not None:
                since = utc_bounds(date_from, date_from, zone)[0]
            if date_to is not None:
                until = utc_bounds(date_to, date_to, zone)[1]
        sessions = await self.sessions.list_sessions(actor.actor_id, limit, offset, since, until)
        sets = await self.sessions.list_sets(actor.actor_id, [s.id for s in sessions])
        sets_by_session: dict[str, list[WorkoutSetLog]] = {}
        for logged in sets:
            sets_by_session.setdefault(logged.session_id, []).append(logged)
        return [_history_item(s, sets_by_session.get(s.id, [])) for s in sessions]

    async def get_history_detail(self, actor: ActorContext, session_id: str) -> WorkoutDetail:
        workout_session = await self._owned_session(actor, session_id)
        sets = await self.sessions.list_sets(actor.actor_id, [workout_session.id])
        exercises_by_id = await self.exercises.get_many(list({s.exercise_id for s in sets if s.exercise_id}))
        return WorkoutDetail(
            **_history_item(workout_session, sets).model_dump(),
            exercises=_history_exercises(sets, {key: e.equipment for key, e in exercises_by_id.items()}),
        )

    async def update_session(
        self, actor: ActorContext, session_id: str, payload: UpdateWorkoutInput
    ) -> WorkoutDetail:
        """Replace a logged workout's name and sets; its start and finish times are kept."""

        workout_session = await self._owned_session(actor, session_id)
        exercises_by_id = await self._verify_exercises_owned(
            actor, [e.exercise_id for e in payload.exercises]
        )

        workout_session.name = payload.name
        workout_session.touch()
        await self.sessions.delete_sets(actor.actor_id, workout_session.id)
        # The bodyweight it was logged at stays: an edit corrects the sets, not the day.
        set_logs = _build_set_logs(workout_session, payload.exercises, exercises_by_id)
        await self.sessions.add_sets(set_logs)
        await self.session.commit()
        return await self.get_history_detail(actor, session_id)

    async def delete_session(self, actor: ActorContext, session_id: str) -> None:
        workout_session = await self._owned_session(actor, session_id)
        await self.sessions.delete_session(workout_session)
        await self.session.commit()
