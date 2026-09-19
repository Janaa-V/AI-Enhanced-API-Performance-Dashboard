"""Application entry point: wires routes, middleware and the resources created at startup."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import Scope

from app.api.errors import register_error_handlers
from app.api.routers.demo import router as demo_router
from app.api.routers.health import router as health_router
from app.config import get_settings
from app.database import Database
from app.middleware.request_logging import RequestLoggingMiddleware
from app.services.request_recorder import RequestRecorder
from app.services.simulation import Simulator


def recorder_from_app_state(scope: Scope) -> RequestRecorder | None:
    """The recorder created at startup; None before startup or after shutdown."""
    return getattr(scope["app"].state, "recorder", None)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = Database(settings)
        application.state.database = database
        application.state.recorder = RequestRecorder(database.sessions)
        application.state.simulator = Simulator(
            latency_scale=settings.simulation_latency_scale,
            failure_scale=settings.simulation_failure_scale,
        )
        try:
            await database.check_connection()
            yield
        finally:
            application.state.recorder = None
            await database.close()

    application = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    # Added first, so it is the innermost layer: CORS preflights never reach it.
    application.add_middleware(RequestLoggingMiddleware, get_recorder=recorder_from_app_state)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    register_error_handlers(application)
    application.include_router(health_router)
    application.include_router(demo_router)
    return application


app = create_app()
