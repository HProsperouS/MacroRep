"""MacroRep FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.body.router import router as body_router
from app.coach.router import router as coach_router
from app.core.config import Settings, get_settings
from app.core.database import dispose_engine, get_engine
from app.food.router import router as food_router
from app.health.router import router as health_router
from app.profile.router import router as profile_router
from app.progress.router import router as progress_router
from app.shared.logging import CorrelationIdMiddleware, configure_logging
from app.shared.persistence import Base
from app.workout.router import router as workout_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.auto_create_schema:
            async with get_engine().begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        if settings.seed_demo_data:
            from app.demo_seed import seed_demo_data

            await seed_demo_data()
        yield
        await dispose_engine()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID", "X-Preview-Actor-Id"],
        expose_headers=["X-Correlation-ID"],
    )
    application.add_middleware(CorrelationIdMiddleware, header_name=settings.correlation_id_header)

    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(profile_router)
    application.include_router(food_router)
    application.include_router(workout_router)
    application.include_router(body_router)
    application.include_router(progress_router)
    application.include_router(coach_router)
    return application


app = create_app()
