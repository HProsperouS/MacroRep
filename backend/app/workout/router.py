"""Exercise catalog, today's plan, and session routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.dependencies import ActorContext, get_current_actor
from app.shared.persistence import get_session
from app.shared.validation import MAX_SEARCH_LENGTH

from .models import EQUIPMENT, MUSCLE_GROUPS
from .repository import ExerciseRepository, WorkoutPlanRepository, WorkoutSessionRepository
from .schemas import (
    CreateExerciseInput,
    ExerciseRead,
    FinishWorkoutInput,
    PlannedWorkout,
    SavePlanDayInput,
    WeekPlanDay,
    WorkoutSummary,
)
from .service import WorkoutService

router = APIRouter(prefix="/api", tags=["workout"])


def get_workout_service(session: Annotated[AsyncSession, Depends(get_session)]) -> WorkoutService:
    return WorkoutService(
        session,
        ExerciseRepository(session),
        WorkoutPlanRepository(session),
        WorkoutSessionRepository(session),
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


@router.get("/workouts/plan", response_model=list[WeekPlanDay])
async def get_week_plan(actor: ActorDep, service: WorkoutServiceDep) -> list[WeekPlanDay]:
    return await service.get_week_plan(actor)


@router.put("/workouts/plan/{day_of_week}", response_model=WeekPlanDay)
async def save_plan_day(
    payload: SavePlanDayInput,
    actor: ActorDep,
    service: WorkoutServiceDep,
    day_of_week: Annotated[int, Path(ge=0, le=6)],
) -> WeekPlanDay:
    return await service.save_day(actor, day_of_week, payload)


@router.delete("/workouts/plan/{day_of_week}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan_day(
    actor: ActorDep, service: WorkoutServiceDep, day_of_week: Annotated[int, Path(ge=0, le=6)]
) -> Response:
    await service.delete_day(actor, day_of_week)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
