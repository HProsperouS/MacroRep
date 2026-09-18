"""Exercise catalog, today's plan, and session-finishing business rules."""

from __future__ import annotations

from datetime import date
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext

from .models import Exercise, SetKind, WorkoutSession, WorkoutSetLog
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
                    sets=[PreviousSet(weight_kg=float(s.weight_kg), reps=s.reps) for s in found[1]],
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
        plan_exercises = await self.plans.list_exercises(plan_entry.id)
        exercise_ids = [plan_exercise.exercise_id for plan_exercise in plan_exercises]
        exercises_by_id = await self.exercises.get_many(exercise_ids)
        last_sessions = await self.exercises.last_session_sets_bulk(actor.actor_id, exercise_ids)

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
                            PreviousSet(weight_kg=float(previous_row.weight_kg), reps=previous_row.reps)
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

        exercises_by_id = await self.exercises.get_many([e.exercise_id for e in payload.exercises])
        for exercise_entry in payload.exercises:
            exercise = exercises_by_id.get(exercise_entry.exercise_id)
            if exercise is None or (exercise.owner_id is not None and exercise.owner_id != actor.actor_id):
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, f"Exercise {exercise_entry.exercise_id} not found"
                )

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
