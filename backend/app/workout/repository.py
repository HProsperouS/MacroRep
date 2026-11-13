"""Owner-scoped exercise, plan, and session persistence."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import cast
from zoneinfo import ZoneInfo

from sqlalchemy import cast as cast_
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.training import estimated_one_rep_max_sql
from app.body.models import WeighIn
from app.shared.db import name_search
from app.shared.persistence.mixins import utc_now
from app.shared.timezones import local_date

from .models import (
    Exercise,
    ExerciseNote,
    SetKind,
    WorkoutPlanEntry,
    WorkoutPlanExercise,
    WorkoutScheduleDay,
    WorkoutSession,
    WorkoutSetLog,
)


class ExerciseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        owner_id: str,
        query: str,
        muscle: str | None,
        equipment: str | None,
        limit: int,
        source: str | None = None,
    ) -> list[Exercise]:
        """The shared library and the user's own exercises; ``source`` keeps only the user's
        own ("custom") or only the library ("library")."""

        filters, ordering = name_search(Exercise.name, query)
        if source == "custom":
            visible = Exercise.owner_id == owner_id
        elif source == "library":
            visible = Exercise.owner_id.is_(None)
        else:
            visible = or_(Exercise.owner_id.is_(None), Exercise.owner_id == owner_id)
        statement = select(Exercise).where(visible, *filters)
        if muscle:
            # Filtered here, before the limit, so no matching exercise is cut off unseen.
            statement = statement.where(cast_(Exercise.muscles, JSONB).contains([muscle]))
        if equipment:
            statement = statement.where(Exercise.equipment == equipment)
        statement = statement.order_by(*ordering).limit(limit)
        return list(await self.session.scalars(statement))

    async def count_custom(self, owner_id: str) -> int:
        statement = select(func.count()).select_from(Exercise).where(Exercise.owner_id == owner_id)
        return int(await self.session.scalar(statement) or 0)

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

    async def notes_bulk(self, owner_id: str, exercise_ids: list[str]) -> dict[str, str]:
        """The user's own notes for several exercises, keyed by exercise id."""

        if not exercise_ids:
            return {}
        rows = await self.session.execute(
            select(ExerciseNote.exercise_id, ExerciseNote.body).where(
                ExerciseNote.owner_id == owner_id, ExerciseNote.exercise_id.in_(exercise_ids)
            )
        )
        return {exercise_id: body for exercise_id, body in rows}

    async def set_note(self, owner_id: str, exercise_id: str, body: str) -> None:
        """Write the user's note on an exercise; an empty body removes it.

        One INSERT ... ON CONFLICT UPDATE, so two quick saves can't both insert a row."""

        if not body:
            await self.session.execute(
                delete(ExerciseNote).where(
                    ExerciseNote.owner_id == owner_id, ExerciseNote.exercise_id == exercise_id
                )
            )
            return
        now = utc_now()
        statement = (
            pg_insert(ExerciseNote)
            .values(
                id=uuid.uuid4().hex, owner_id=owner_id, exercise_id=exercise_id, body=body, created_utc=now
            )
            .on_conflict_do_update(
                index_elements=[ExerciseNote.owner_id, ExerciseNote.exercise_id],
                set_={"body": body, "updated_utc": now},
            )
        )
        await self.session.execute(statement)

    async def last_session_sets_bulk(
        self, owner_id: str, exercise_ids: list[str], zone: ZoneInfo
    ) -> dict[str, tuple[str, list[WorkoutSetLog]]]:
        """The most recent logged session's sets for several exercises, in two queries
        total instead of one round trip per exercise. Dated in the user's ``zone``."""

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
            row.exercise_id: (
                local_date(row.started_at, zone).isoformat(),
                sets_by_session.get(row.session_id, []),
            )
            for row in latest_rows
        }


class WorkoutPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_day(self, owner_id: str, day_of_week: int) -> WorkoutPlanEntry | None:
        """The routine scheduled on a weekday, or None on a rest day."""

        return cast(
            "WorkoutPlanEntry | None",
            await self.session.scalar(
                select(WorkoutPlanEntry)
                .join(WorkoutScheduleDay, WorkoutScheduleDay.routine_id == WorkoutPlanEntry.id)
                .where(WorkoutScheduleDay.owner_id == owner_id, WorkoutScheduleDay.day_of_week == day_of_week)
            ),
        )

    async def get(self, plan_entry_id: str) -> WorkoutPlanEntry | None:
        return await self.session.get(WorkoutPlanEntry, plan_entry_id)

    async def get_many(self, plan_entry_ids: list[str]) -> dict[str, WorkoutPlanEntry]:
        """Several routines by id, keyed by id, leaving out any that don't exist."""

        if not plan_entry_ids:
            return {}
        rows = await self.session.scalars(
            select(WorkoutPlanEntry).where(WorkoutPlanEntry.id.in_(plan_entry_ids))
        )
        return {row.id: row for row in rows}

    async def list_for_owner(self, owner_id: str) -> list[WorkoutPlanEntry]:
        return list(
            await self.session.scalars(
                select(WorkoutPlanEntry)
                .where(WorkoutPlanEntry.owner_id == owner_id)
                .order_by(WorkoutPlanEntry.name.asc(), WorkoutPlanEntry.id)
            )
        )

    async def count_for_owner(self, owner_id: str) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(WorkoutPlanEntry)
                .where(WorkoutPlanEntry.owner_id == owner_id)
            )
            or 0
        )

    async def add(self, plan_entry: WorkoutPlanEntry) -> WorkoutPlanEntry:
        self.session.add(plan_entry)
        await self.session.flush()
        return plan_entry

    async def delete(self, plan_entry: WorkoutPlanEntry) -> None:
        """Remove a routine. The database removes its exercises and schedule days with it (ON
        DELETE CASCADE) and keeps logged workouts, unlinked (SET NULL)."""

        await self.session.delete(plan_entry)
        await self.session.flush()

    async def list_schedule(self, owner_id: str) -> list[WorkoutScheduleDay]:
        return list(
            await self.session.scalars(
                select(WorkoutScheduleDay).where(WorkoutScheduleDay.owner_id == owner_id)
            )
        )

    async def set_day(self, owner_id: str, day_of_week: int, routine_id: str) -> None:
        """Schedule a routine on a weekday, replacing whatever was there.

        One INSERT ... ON CONFLICT UPDATE, not a SELECT then a write: two
        requests scheduling the same day at once can't both land their own row.
        """

        statement = (
            pg_insert(WorkoutScheduleDay)
            .values(owner_id=owner_id, day_of_week=day_of_week, routine_id=routine_id)
            .on_conflict_do_update(
                index_elements=[WorkoutScheduleDay.owner_id, WorkoutScheduleDay.day_of_week],
                set_={"routine_id": routine_id},
            )
        )
        await self.session.execute(statement)

    async def clear_day(self, owner_id: str, day_of_week: int) -> None:
        await self.session.execute(
            delete(WorkoutScheduleDay).where(
                WorkoutScheduleDay.owner_id == owner_id, WorkoutScheduleDay.day_of_week == day_of_week
            )
        )

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

    async def delete_sets(self, owner_id: str, session_id: str) -> None:
        await self.session.execute(
            delete(WorkoutSetLog).where(
                WorkoutSetLog.owner_id == owner_id, WorkoutSetLog.session_id == session_id
            )
        )

    async def delete_session(self, workout_session: WorkoutSession) -> None:
        # The database removes its sets with it (ON DELETE CASCADE).
        await self.session.delete(workout_session)
        await self.session.flush()

    async def list_sessions(
        self,
        owner_id: str,
        limit: int,
        offset: int,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[WorkoutSession]:
        """Newest first; the id breaks ties so paging never repeats or skips a session.

        ``since``/``until`` keep sessions started in ``[since, until)``."""

        statement = select(WorkoutSession).where(WorkoutSession.owner_id == owner_id)
        if since is not None:
            statement = statement.where(WorkoutSession.started_at >= since)
        if until is not None:
            statement = statement.where(WorkoutSession.started_at < until)
        return list(
            await self.session.scalars(
                statement.order_by(WorkoutSession.started_at.desc(), WorkoutSession.id)
                .limit(limit)
                .offset(offset)
            )
        )

    async def get_session(self, owner_id: str, session_id: str) -> WorkoutSession | None:
        workout_session: WorkoutSession | None = await self.session.scalar(
            select(WorkoutSession).where(WorkoutSession.id == session_id, WorkoutSession.owner_id == owner_id)
        )
        return workout_session

    async def list_sets(self, owner_id: str, session_ids: list[str]) -> list[WorkoutSetLog]:
        if not session_ids:
            return []
        return list(
            await self.session.scalars(
                select(WorkoutSetLog)
                .where(WorkoutSetLog.owner_id == owner_id, WorkoutSetLog.session_id.in_(session_ids))
                .order_by(WorkoutSetLog.position.asc())
            )
        )

    async def body_weight_on(self, owner_id: str, day: date) -> float | None:
        """The latest weigh-in on or before ``day``: what bodyweight sets that day count."""

        weight = await self.session.scalar(
            select(WeighIn.weight_kg)
            .where(WeighIn.owner_id == owner_id, WeighIn.log_date <= day)
            .order_by(WeighIn.log_date.desc())
            .limit(1)
        )
        return None if weight is None else float(weight)

    async def best_reps_before(
        self, owner_id: str, exercise_ids: list[str], before_session_id: str
    ) -> dict[str, int]:
        """The most reps in one set with no load (a band) per exercise, from sessions before
        this one: the record a rep-based set is judged against. Warm-ups don't count."""

        if not exercise_ids:
            return {}
        statement = (
            select(WorkoutSetLog.exercise_id, func.max(WorkoutSetLog.reps))
            .where(
                WorkoutSetLog.owner_id == owner_id,
                WorkoutSetLog.exercise_id.in_(exercise_ids),
                WorkoutSetLog.session_id != before_session_id,
                WorkoutSetLog.kind != SetKind.WARMUP,
                WorkoutSetLog.load_kg <= 0,
            )
            .group_by(WorkoutSetLog.exercise_id)
        )
        return {
            exercise_id: int(best)
            for exercise_id, best in await self.session.execute(statement)
            if exercise_id is not None and best is not None
        }

    async def best_e1rms_before(
        self, owner_id: str, exercise_ids: list[str], before_session_id: str
    ) -> dict[str, float]:
        """The best estimated 1RM (Epley) per exercise from working sets in sessions
        before this one, aggregated by the database: one row per exercise, not every
        set ever logged hydrated to be reduced in Python.

        Filtered to working sets only, matching the new-PR comparison in
        ``WorkoutService.finish_session`` — otherwise a heavy warmup could inflate
        this baseline and mask a genuine working-set PR.
        """

        if not exercise_ids:
            return {}
        e1rm = estimated_one_rep_max_sql(WorkoutSetLog.load_kg, WorkoutSetLog.reps)
        statement = (
            select(WorkoutSetLog.exercise_id, func.max(e1rm))
            .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
            .where(
                WorkoutSetLog.owner_id == owner_id,
                WorkoutSetLog.exercise_id.in_(exercise_ids),
                WorkoutSetLog.session_id != before_session_id,
                WorkoutSetLog.kind != SetKind.WARMUP,
            )
            .group_by(WorkoutSetLog.exercise_id)
        )
        return {
            exercise_id: float(best)
            for exercise_id, best in await self.session.execute(statement)
            if best is not None
        }
