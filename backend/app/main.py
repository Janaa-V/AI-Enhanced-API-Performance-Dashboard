"""Application entry point: wires routes, middleware and the resources created at startup."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import Scope

from app.api.errors import register_error_handlers
from app.api.routers.analysis import router as analysis_router
from app.api.routers.demo import router as demo_router
from app.api.routers.health import router as health_router
from app.api.routers.metrics import router as metrics_router
from app.config import Settings, get_settings
from app.database import Database
from app.middleware.request_logging import RequestLoggingMiddleware
from app.services.analysis.guard import build_analyzer
from app.services.request_recorder import RequestRecorder
from app.services.simulation import DEFAULT_PROFILES, DEMO_DEGRADATION, Simulator

logger = logging.getLogger(__name__)


def build_simulator(settings: Settings) -> Simulator:
    """The demo simulator, with one endpoint made slow and flaky on purpose if configured."""
    name = settings.simulation_degraded_endpoint
    if name is not None:
        # Loud, so nobody mistakes a demo setting for a real regression.
        logger.warning(
            "Demo degradation is on: %s is %gx slower and fails at least %.0f%% of requests.",
            name,
            DEMO_DEGRADATION.latency_factor,
            DEMO_DEGRADATION.failure_rate * 100,
        )
    return Simulator(
        latency_scale=settings.simulation_latency_scale,
        failure_scale=settings.simulation_failure_scale,
        degraded=DEFAULT_PROFILES[name] if name is not None else None,
    )


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
        application.state.simulator = build_simulator(settings)
        # One client for every provider call, so connections to the provider are reused.
        http_client = httpx2.AsyncClient(timeout=settings.ai_timeout_seconds)
        application.state.analyzer = build_analyzer(settings, http_client)
        try:
            await database.check_connection()
            yield
        finally:
            application.state.recorder = None
            await http_client.aclose()
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
    application.include_router(metrics_router)
    application.include_router(analysis_router)
    return application


app = create_app()
