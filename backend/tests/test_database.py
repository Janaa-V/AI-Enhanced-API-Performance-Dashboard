"""Verify database lifecycle and readiness without requiring a live server."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.database import Database
from app.main import create_app


@pytest.mark.asyncio
async def test_database_url_preserves_special_password_characters() -> None:
    database = Database(Settings(db_password="password@:/?#", _env_file=None))
    try:
        assert database.engine.url.password == "password@:/?#"
        assert database.engine.url.drivername == "postgresql+psycopg"
        assert "password@:/?#" not in repr(database.engine.url)
    finally:
        await database.close()


def test_missing_database_password_fails_clearly() -> None:
    with pytest.raises(ValueError, match="DB_PASSWORD"):
        Database(Settings(_env_file=None))


def test_health_and_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    database = AsyncMock()
    monkeypatch.setattr("app.main.Database", lambda settings: database)
    with TestClient(create_app()) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok"}
        assert database.check_connection.await_count == 2
    database.close.assert_awaited_once()


def test_health_failure_hides_connection_details(monkeypatch: pytest.MonkeyPatch) -> None:
    database = AsyncMock()
    database.check_connection.side_effect = [
        None,
        OperationalError("SELECT 1", {}, Exception("private connection details")),
    ]
    monkeypatch.setattr("app.main.Database", lambda settings: database)
    with TestClient(create_app()) as client:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
    database.close.assert_awaited_once()


def test_startup_failure_disposes_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    database = AsyncMock()
    database.check_connection.side_effect = RuntimeError("connection failed")
    monkeypatch.setattr("app.main.Database", lambda settings: database)
    with pytest.raises(RuntimeError, match="connection failed"), TestClient(create_app()):
        pass
    database.close.assert_awaited_once()
