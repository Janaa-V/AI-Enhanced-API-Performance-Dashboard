"""Verify how the app connects the request logging, without needing a database."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx2
import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import build_simulator, create_app, recorder_from_app_state
from app.middleware.request_logging import RequestLoggingMiddleware
from app.services.simulation import DEFAULT_PROFILES


def scope_with(state: object) -> dict:
    return {"app": SimpleNamespace(state=state)}


def test_the_recorder_is_found_on_the_app_state() -> None:
    recorder = object()
    assert recorder_from_app_state(scope_with(SimpleNamespace(recorder=recorder))) is recorder


def test_no_recorder_before_startup() -> None:
    assert recorder_from_app_state(scope_with(SimpleNamespace())) is None


def test_no_recorder_after_shutdown() -> None:
    assert recorder_from_app_state(scope_with(SimpleNamespace(recorder=None))) is None


def test_logging_sits_inside_cors_so_preflights_never_reach_it() -> None:
    """Middleware is listed outermost first."""
    kinds = [middleware.cls for middleware in create_app().user_middleware]
    assert kinds.index(CORSMiddleware) < kinds.index(RequestLoggingMiddleware)


def test_the_recorder_exists_while_the_app_runs_and_is_cleared_at_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = AsyncMock()
    created: list[object] = []

    def fake_recorder(sessions: object) -> object:
        created.append(sessions)
        return object()

    monkeypatch.setattr("app.main.Database", lambda settings: database)
    monkeypatch.setattr("app.main.RequestRecorder", fake_recorder)
    application = create_app()
    with TestClient(application):
        assert application.state.recorder is not None
        assert created == [database.sessions]  # built from the application's own sessions
    assert application.state.recorder is None


# --- the simulator built from settings ------------------------------------------

REPORTS = DEFAULT_PROFILES["reports"]  # normally 400-1500 ms


def report_delays(settings: Settings) -> list[float]:
    simulator = build_simulator(settings)
    return [simulator.plan(REPORTS).delay_seconds for _ in range(200)]


def test_the_simulator_is_healthy_by_default(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        delays = report_delays(Settings(_env_file=None))
    assert max(delays) <= 1.5
    assert caplog.records == []


def test_the_configured_endpoint_is_degraded_and_a_warning_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        delays = report_delays(Settings(_env_file=None, simulation_degraded_endpoint="reports"))
    assert min(delays) >= 1.2
    assert max(delays) > 1.5
    [record] = caplog.records
    assert "reports" in record.getMessage() and "3x slower" in record.getMessage()


def test_the_scales_from_settings_still_apply() -> None:
    delays = report_delays(Settings(_env_file=None, simulation_latency_scale=0))
    assert set(delays) == {0}


# --- the analyzer and its HTTP client ------------------------------------------------


def test_the_analyzer_gets_one_client_that_is_closed_at_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients: list[httpx2.AsyncClient] = []

    def fake_build(settings: Settings, client: httpx2.AsyncClient) -> object:
        clients.append(client)
        return object()

    monkeypatch.setattr("app.main.Database", lambda settings: AsyncMock())
    monkeypatch.setattr("app.main.build_analyzer", fake_build)
    application = create_app()
    with TestClient(application):
        [client] = clients
        assert application.state.analyzer is not None
        assert not client.is_closed
    assert client.is_closed
