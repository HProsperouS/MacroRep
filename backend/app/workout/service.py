"""Exercise catalog, today's plan, and session-finishing business rules."""

from __future__ import annotations

from datetime import date
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext

from .models import Exercise, SetKind, WorkoutPlanEntry, WorkoutPlanExercise, WorkoutSession, WorkoutSetLog
from .repository import ExerciseRepository, WorkoutPlanRepository, WorkoutSessionRepository
from .schemas import (
    CreateExerciseInput,
    ExerciseRead,
    FinishWorkoutInput,
    LastSession,
    PlannedExercise,
    PlannedSet,
    PlannedWorkout,
    PreviousSet,
    SavePlanDayInput,
    WeekPlanDay,
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


class WorkoutService:
    def __init__(
        self,
        session: AsyncSession,
        exercises: ExerciseRepository,
        plans: WorkoutPlanRepository,
        sessions: WorkoutSessionRepository,
    ) -> None:
        self.session = session
        self.exercises = exercises
        self.plans = plans
        self.sessions = sessions

    async def search_exercises(
        self, actor: ActorContext, query: str, muscle: str | None, equipment: str | None, limit: int
    ) -> list[ExerciseRead]:
        rows = await self.exercises.search(actor.actor_id, query, equipment, limit)
        if muscle:
            rows = [row for row in rows if muscle in row.muscles]
        rows = rows[:limit]

        last_sessions = await self.exercises.last_session_sets_bulk(actor.actor_id, [row.id for row in rows])
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
        day_of_week = date.today().weekday()
        plan_entry = await self.plans.get_for_day(actor.actor_id, day_of_week)
        if plan_entry is None:
            return None
        return await self._build_planned_workout(plan_entry, actor)

    async def get_week_plan(self, actor: ActorContext) -> list[WeekPlanDay]:
        entries = await self.plans.list_for_owner(actor.actor_id)
        entries_by_day = {entry.day_of_week: entry for entry in entries}

        # Batched across all 7 days (a handful of queries total) rather than
        # calling _build_planned_workout per day, which would otherwise run
        # its own 3 queries per day — up to 21 sequential round trips here.
        plan_exercises_by_entry = await self.plans.list_exercises_for_entries([entry.id for entry in entries])
        all_exercise_ids = [pe.exercise_id for pes in plan_exercises_by_entry.values() for pe in pes]
        exercises_by_id = await self.exercises.get_many(all_exercise_ids)
        last_sessions = await self.exercises.last_session_sets_bulk(actor.actor_id, all_exercise_ids)

        result: list[WeekPlanDay] = []
        for day_of_week in range(7):
            entry = entries_by_day.get(day_of_week)
            plan = (
                self._assemble_planned_workout(
                    entry, plan_exercises_by_entry[entry.id], exercises_by_id, last_sessions
                )
                if entry is not None
                else None
            )
            result.append(WeekPlanDay(day_of_week=day_of_week, plan=plan))
        return result

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

    async def save_day(self, actor: ActorContext, day_of_week: int, payload: SavePlanDayInput) -> WeekPlanDay:
        exercises_by_id = await self._verify_exercises_owned(
            actor, [e.exercise_id for e in payload.exercises]
        )

        plan_entry = await self.plans.get_for_day(actor.actor_id, day_of_week)
        if plan_entry is None:
            plan_entry = WorkoutPlanEntry(
                owner_id=actor.actor_id,
                day_of_week=day_of_week,
                name=payload.name,
                week_label=payload.week_label,
                estimated_minutes=payload.estimated_minutes,
            )
            try:
                await self.plans.add(plan_entry)
            except IntegrityError:
                # Lost a race with a concurrent save for this same day (e.g. a
                # double-submit) — the unique (owner_id, day_of_week) index
                # rejected the second insert. Ask the client to retry rather
                # than surfacing a raw 500; a retry will see the row that won
                # and take the update branch below instead.
                await self.session.rollback()
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "This day was just saved elsewhere, please retry"
                ) from None
        else:
            plan_entry.name = payload.name
            plan_entry.week_label = payload.week_label
            plan_entry.estimated_minutes = payload.estimated_minutes
            plan_entry.touch()

        new_exercises = [
            WorkoutPlanExercise(
                plan_entry_id=plan_entry.id,
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
        await self.plans.replace_exercises(plan_entry.id, new_exercises)
        await self.session.commit()

        # Assemble from what we already have in memory (new_exercises, exercises_by_id)
        # instead of re-querying them via _build_planned_workout — only the last-session
        # data is actually new here.
        last_sessions = await self.exercises.last_session_sets_bulk(
            actor.actor_id, [e.exercise_id for e in payload.exercises]
        )
        plan = self._assemble_planned_workout(plan_entry, new_exercises, exercises_by_id, last_sessions)
        return WeekPlanDay(day_of_week=day_of_week, plan=plan)

    async def delete_day(self, actor: ActorContext, day_of_week: int) -> None:
        plan_entry = await self.plans.get_for_day(actor.actor_id, day_of_week)
        if plan_entry is None:
            return
        await self.plans.delete(plan_entry)
        await self.session.commit()

    async def _build_planned_workout(
        self, plan_entry: WorkoutPlanEntry, actor: ActorContext
    ) -> PlannedWorkout:
        plan_exercises = await self.plans.list_exercises(plan_entry.id)
        exercise_ids = [plan_exercise.exercise_id for plan_exercise in plan_exercises]
        exercises_by_id = await self.exercises.get_many(exercise_ids)
        last_sessions = await self.exercises.last_session_sets_bulk(actor.actor_id, exercise_ids)
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
            # Match previous sets to planned sets by kind (warmup/working), not raw list
            # position — a past session with a different set layout would otherwise pair
            # a planned warmup with what was actually a working set's numbers.
            previous_by_kind: dict[SetKind, list[WorkoutSetLog]] = {}
            for row in previous_sets:
                previous_by_kind.setdefault(row.kind, []).append(row)
            next_index_by_kind: dict[SetKind, int] = {}

            sets: list[PlannedSet] = []
            for index, planned in enumerate(plan_exercise.planned_sets):
                kind = cast(SetKind, planned["kind"])
                bucket = previous_by_kind.get(kind, [])
                cursor = next_index_by_kind.get(kind, 0)
                previous_row = bucket[cursor] if cursor < len(bucket) else None
                if previous_row is not None:
                    next_index_by_kind[kind] = cursor + 1
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
        if payload.plan_id is not None:
            plan_entry = await self.plans.get(payload.plan_id)
            if plan_entry is None or plan_entry.owner_id != actor.actor_id:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Workout plan not found")

        await self._verify_exercises_owned(actor, [e.exercise_id for e in payload.exercises])

        workout_session = WorkoutSession(
            owner_id=actor.actor_id,
            plan_entry_id=payload.plan_id,
            name=payload.name,
            started_at=payload.started_at,
            finished_at=payload.finished_at,
        )
        await self.sessions.add_session(workout_session)

        set_logs: list[WorkoutSetLog] = []
        for exercise_entry in payload.exercises:
            for index, logged_set in enumerate(exercise_entry.sets):
                set_logs.append(
                    WorkoutSetLog(
                        session_id=workout_session.id,
                        owner_id=actor.actor_id,
                        exercise_id=exercise_entry.exercise_id,
                        exercise_name=exercise_entry.name,
                        kind=logged_set.kind,
                        weight_kg=logged_set.weight_kg,
                        reps=logged_set.reps,
                        rpe=logged_set.rpe,
                        position=index,
                    )
                )
        await self.sessions.add_sets(set_logs)

        best_before_by_exercise = await self.sessions.best_e1rms_before(
            actor.actor_id, [e.exercise_id for e in payload.exercises], workout_session.id
        )
        personal_records: list[str] = []
        for exercise_entry in payload.exercises:
            working_sets = [s for s in exercise_entry.sets if s.kind == SetKind.WORKING]
            if not working_sets:
                continue
            best_new = max(s.weight_kg * (1 + s.reps / 30) for s in working_sets)
            best_before = best_before_by_exercise.get(exercise_entry.exercise_id)
            if best_before is None or best_new > best_before:
                personal_records.append(f"{exercise_entry.name} — new estimated 1RM {round(best_new, 1)} kg")

        volume_kg = sum(s.weight_kg * s.reps for e in payload.exercises for s in e.sets)
        sets_completed = sum(len(e.sets) for e in payload.exercises)
        duration_seconds = int((payload.finished_at - payload.started_at).total_seconds())

        await self.session.commit()
        return WorkoutSummary(
            id=workout_session.id,
            name=workout_session.name,
            duration_seconds=max(duration_seconds, 0),
            sets_completed=sets_completed,
            volume_kg=round(volume_kg, 1),
            personal_records=personal_records,
        )
