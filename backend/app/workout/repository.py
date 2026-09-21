"""Owner-scoped exercise, plan, and session persistence."""

from __future__ import annotations

from typing import cast

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db import escape_like

from .models import (
    Exercise,
    SetKind,
    WorkoutPlanEntry,
    WorkoutPlanExercise,
    WorkoutSession,
    WorkoutSetLog,
)


class ExerciseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(self, owner_id: str, query: str, equipment: str | None, limit: int) -> list[Exercise]:
        statement = select(Exercise).where(or_(Exercise.owner_id.is_(None), Exercise.owner_id == owner_id))
        if query:
            pattern = f"%{escape_like(query.strip())}%"
            statement = statement.where(Exercise.name.ilike(pattern, escape="\\"))
        if equipment:
            statement = statement.where(Exercise.equipment == equipment)
        statement = statement.order_by(Exercise.name.asc()).limit(max(limit * 3, limit))
        return list(await self.session.scalars(statement))

    async def get(self, exercise_id: str) -> Exercise | None:
        return await self.session.get(Exercise, exercise_id)

    async def get_many(self, exercise_ids: list[str]) -> dict[str, Exercise]:
        if not exercise_ids:
            return {}
        rows = await self.session.scalars(select(Exercise).where(Exercise.id.in_(exercise_ids)))
        return {row.id: row for row in rows}

    async def add(self, exercise: Exercise) -> Exercise:
        self.session.add(exercise)
        await self.session.flush()
        return exercise

    async def last_session_sets_bulk(
        self, owner_id: str, exercise_ids: list[str]
    ) -> dict[str, tuple[str, list[WorkoutSetLog]]]:
        """The most recent logged session's sets for several exercises, in two queries
        total instead of one round trip per exercise."""

        if not exercise_ids:
            return {}

        distinct_sessions = (
            select(
                WorkoutSetLog.exercise_id.label("exercise_id"),
                WorkoutSetLog.session_id.label("session_id"),
                WorkoutSession.started_at.label("started_at"),
            )
            .distinct()
            .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
            .where(WorkoutSetLog.owner_id == owner_id, WorkoutSetLog.exercise_id.in_(exercise_ids))
            .subquery()
        )
        ranked = select(
            distinct_sessions.c.exercise_id,
            distinct_sessions.c.session_id,
            distinct_sessions.c.started_at,
            func.row_number()
            .over(
                partition_by=distinct_sessions.c.exercise_id, order_by=distinct_sessions.c.started_at.desc()
            )
            .label("rn"),
        ).subquery()
        latest = select(ranked.c.exercise_id, ranked.c.session_id, ranked.c.started_at).where(
            ranked.c.rn == 1
        )
        latest_rows = list(await self.session.execute(latest))
        if not latest_rows:
            return {}

        session_ids = [row.session_id for row in latest_rows]
        set_rows = list(
            await self.session.scalars(
                select(WorkoutSetLog)
                .where(WorkoutSetLog.session_id.in_(session_ids), WorkoutSetLog.exercise_id.in_(exercise_ids))
                .order_by(WorkoutSetLog.position.asc())
            )
        )
        sets_by_session: dict[str, list[WorkoutSetLog]] = {}
        for row in set_rows:
            sets_by_session.setdefault(row.session_id, []).append(row)

        return {
            row.exercise_id: (row.started_at.date().isoformat(), sets_by_session.get(row.session_id, []))
            for row in latest_rows
        }


class WorkoutPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_day(self, owner_id: str, day_of_week: int) -> WorkoutPlanEntry | None:
        return cast(
            "WorkoutPlanEntry | None",
            await self.session.scalar(
                select(WorkoutPlanEntry).where(
                    WorkoutPlanEntry.owner_id == owner_id, WorkoutPlanEntry.day_of_week == day_of_week
                )
            ),
        )

    async def get(self, plan_entry_id: str) -> WorkoutPlanEntry | None:
        return await self.session.get(WorkoutPlanEntry, plan_entry_id)

    async def list_for_owner(self, owner_id: str) -> list[WorkoutPlanEntry]:
        return list(
            await self.session.scalars(select(WorkoutPlanEntry).where(WorkoutPlanEntry.owner_id == owner_id))
        )

    async def add(self, plan_entry: WorkoutPlanEntry) -> WorkoutPlanEntry:
        self.session.add(plan_entry)
        await self.session.flush()
        return plan_entry

    async def delete(self, plan_entry: WorkoutPlanEntry) -> None:
        await self.session.delete(plan_entry)

    async def list_exercises(self, plan_entry_id: str) -> list[WorkoutPlanExercise]:
        return list(
            await self.session.scalars(
                select(WorkoutPlanExercise)
                .where(WorkoutPlanExercise.plan_entry_id == plan_entry_id)
                .order_by(WorkoutPlanExercise.position.asc())
            )
        )

    async def list_exercises_for_entries(
        self, plan_entry_ids: list[str]
    ) -> dict[str, list[WorkoutPlanExercise]]:
        """Batched form of :meth:`list_exercises` for several plan entries at once."""

        if not plan_entry_ids:
            return {}
        rows = await self.session.scalars(
            select(WorkoutPlanExercise)
            .where(WorkoutPlanExercise.plan_entry_id.in_(plan_entry_ids))
            .order_by(WorkoutPlanExercise.position.asc())
        )
        grouped: dict[str, list[WorkoutPlanExercise]] = {entry_id: [] for entry_id in plan_entry_ids}
        for row in rows:
            grouped[row.plan_entry_id].append(row)
        return grouped

    async def replace_exercises(self, plan_entry_id: str, exercises: list[WorkoutPlanExercise]) -> None:
        """Delete a day's existing exercise list and insert the new one, as one unit."""

        await self.session.execute(
            delete(WorkoutPlanExercise).where(WorkoutPlanExercise.plan_entry_id == plan_entry_id)
        )
        self.session.add_all(exercises)
        await self.session.flush()


class WorkoutSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_session(self, workout_session: WorkoutSession) -> WorkoutSession:
        self.session.add(workout_session)
        await self.session.flush()
        return workout_session

    async def add_sets(self, set_logs: list[WorkoutSetLog]) -> None:
        self.session.add_all(set_logs)
        await self.session.flush()

    async def best_e1rms_before(
        self, owner_id: str, exercise_ids: list[str], before_session_id: str
    ) -> dict[str, float]:
        """The best estimated 1RM (Epley) per exercise from working sets in sessions
        before this one, in one query for all exercises at once.

        Filtered to working sets only, matching the new-PR comparison in
        ``WorkoutService.finish_session`` — otherwise a heavy warmup could inflate
        this baseline and mask a genuine working-set PR.
        """

        if not exercise_ids:
            return {}
        rows = list(
            await self.session.scalars(
                select(WorkoutSetLog)
                .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
                .where(
                    WorkoutSetLog.owner_id == owner_id,
                    WorkoutSetLog.exercise_id.in_(exercise_ids),
                    WorkoutSetLog.session_id != before_session_id,
                    WorkoutSetLog.kind == SetKind.WORKING,
                )
            )
        )
        best: dict[str, float] = {}
        for row in rows:
            e1rm = float(row.weight_kg) * (1 + row.reps / 30)
            if row.exercise_id is not None:
                best[row.exercise_id] = max(best.get(row.exercise_id, 0.0), e1rm)
        return best
