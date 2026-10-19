"""Exercise catalog, today's plan, and session routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.identity.dependencies import ActorContext, get_current_actor
from app.profile.repository import ProfileRepository
from app.shared.validation import MAX_SEARCH_LENGTH

from .models import EQUIPMENT, MUSCLE_GROUPS
from .repository import ExerciseRepository, WorkoutPlanRepository, WorkoutSessionRepository
from .schemas import (
    AssignDayInput,
    CreateExerciseInput,
    ExerciseRead,
    FinishWorkoutInput,
    PlannedWorkout,
    RoutineRead,
    SaveRoutineInput,
    UpdateWorkoutInput,
    WeekPlanDay,
    WorkoutDetail,
    WorkoutHistoryItem,
    WorkoutSummary,
)
from .service import WorkoutService

router = APIRouter(prefix="/api/v1", tags=["workout"])


def get_workout_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> WorkoutService:
    return WorkoutService(
        session,
        ExerciseRepository(session),
        WorkoutPlanRepository(session),
        WorkoutSessionRepository(session),
        ProfileRepository(session),
    )


WorkoutServiceDep = Annotated[WorkoutService, Depends(get_workout_service)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("/workouts/today", response_model=PlannedWorkout | None)
async def get_today(actor: ActorDep, service: WorkoutServiceDep) -> PlannedWorkout | None:
    return await service.get_today(actor)


@router.get("/exercises", response_model=list[ExerciseRead])
async def search_exercises(
    actor: ActorDep,
    service: WorkoutServiceDep,
    q: Annotated[str, Query(max_length=MAX_SEARCH_LENGTH)] = "",
    muscle: Annotated[str | None, Query()] = None,
    equipment: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[ExerciseRead]:
    if equipment is not None and equipment not in EQUIPMENT:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"equipment must be one of {EQUIPMENT}")
    if muscle is not None and muscle not in MUSCLE_GROUPS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"muscle must be one of {MUSCLE_GROUPS}")
    return await service.search_exercises(actor, q, muscle, equipment, limit)


@router.post("/exercises", response_model=ExerciseRead, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    payload: CreateExerciseInput, actor: ActorDep, service: WorkoutServiceDep
) -> ExerciseRead:
    return await service.create_exercise(payload, actor)


@router.post("/workouts/sessions", response_model=WorkoutSummary, status_code=status.HTTP_201_CREATED)
async def finish_session(
    payload: FinishWorkoutInput, actor: ActorDep, service: WorkoutServiceDep
) -> WorkoutSummary:
    return await service.finish_session(payload, actor)


@router.get("/workouts/sessions", response_model=list[WorkoutHistoryItem])
async def list_sessions(
    actor: ActorDep,
    service: WorkoutServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> list[WorkoutHistoryItem]:
    """Logged workouts, newest first."""

    return await service.list_history(actor, limit, offset)


@router.get("/workouts/sessions/{session_id}", response_model=WorkoutDetail)
async def get_session_detail(session_id: str, actor: ActorDep, service: WorkoutServiceDep) -> WorkoutDetail:
    return await service.get_history_detail(actor, session_id)


@router.put("/workouts/sessions/{session_id}", response_model=WorkoutDetail)
async def update_session(
    session_id: str, payload: UpdateWorkoutInput, actor: ActorDep, service: WorkoutServiceDep
) -> WorkoutDetail:
    return await service.update_session(actor, session_id, payload)


@router.delete("/workouts/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, actor: ActorDep, service: WorkoutServiceDep) -> Response:
    await service.delete_session(actor, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/workouts/plan", response_model=list[WeekPlanDay])
async def get_week_plan(actor: ActorDep, service: WorkoutServiceDep) -> list[WeekPlanDay]:
    return await service.get_week_plan(actor)


@router.put("/workouts/plan/{day_of_week}", response_model=WeekPlanDay)
async def assign_plan_day(
    payload: AssignDayInput,
    actor: ActorDep,
    service: WorkoutServiceDep,
    day_of_week: Annotated[int, Path(ge=0, le=6)],
) -> WeekPlanDay:
    """Schedule one of the user's routines on a weekday."""

    return await service.assign_day(actor, day_of_week, payload)


@router.delete("/workouts/plan/{day_of_week}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_plan_day(
    actor: ActorDep, service: WorkoutServiceDep, day_of_week: Annotated[int, Path(ge=0, le=6)]
) -> Response:
    """Make a weekday a rest day. The routine itself is kept."""

    await service.clear_day(actor, day_of_week)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/workouts/routines", response_model=list[RoutineRead])
async def list_routines(actor: ActorDep, service: WorkoutServiceDep) -> list[RoutineRead]:
    return await service.list_routines(actor)


@router.post("/workouts/routines", response_model=RoutineRead, status_code=status.HTTP_201_CREATED)
async def create_routine(
    payload: SaveRoutineInput, actor: ActorDep, service: WorkoutServiceDep
) -> RoutineRead:
    return await service.create_routine(actor, payload)


@router.put("/workouts/routines/{routine_id}", response_model=RoutineRead)
async def update_routine(
    routine_id: str, payload: SaveRoutineInput, actor: ActorDep, service: WorkoutServiceDep
) -> RoutineRead:
    return await service.update_routine(actor, routine_id, payload)


@router.delete("/workouts/routines/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routine(routine_id: str, actor: ActorDep, service: WorkoutServiceDep) -> Response:
    await service.delete_routine(actor, routine_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
