"""Verify how the app connects the request logging, without needing a database."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.main import create_app, recorder_from_app_state
from app.middleware.request_logging import RequestLoggingMiddleware


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
