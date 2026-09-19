"""Verify the request_logs schema against a real PostgreSQL database."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.database import Database, build_database_url
from app.models import Base, RequestLog

pytestmark = pytest.mark.integration


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "endpoint": "/demo/users",
        "method": "GET",
        "status_code": 200,
        "latency_ms": 12.5,
        "started_at": datetime.now(UTC),
    }
    return row | overrides


async def test_models_match_the_migrated_schema(db: Database) -> None:
    """Fails when a model changes without a matching migration."""

    def find_differences(connection: Any) -> list[Any]:
        return compare_metadata(MigrationContext.configure(connection), Base.metadata)

    async with db.engine.connect() as connection:
        assert await connection.run_sync(find_differences) == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"status_code": 99},
        {"status_code": 600},
        {"latency_ms": -0.1},
        {"endpoint": None},
        {"method": None},
        {"status_code": None},
        {"latency_ms": None},
        {"started_at": None},
    ],
    ids=[
        "status-below-100",
        "status-above-599",
        "negative-latency",
        "null-endpoint",
        "null-method",
        "null-status",
        "null-latency",
        "null-started-at",
    ],
)
async def test_database_rejects_invalid_rows(db: Database, overrides: dict[str, Any]) -> None:
    async with db.sessions() as session:
        session.add(RequestLog(**_row(**overrides)))
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.parametrize(
    "overrides",
    [{"status_code": 100}, {"status_code": 599}, {"latency_ms": 0}],
    ids=["lowest-status", "highest-status", "zero-latency"],
)
async def test_database_accepts_boundary_values(db: Database, overrides: dict[str, Any]) -> None:
    async with db.sessions() as session:
        session.add(RequestLog(**_row(**overrides)))
        await session.commit()


async def test_timestamp_keeps_the_same_instant_across_time_zones(db: Database) -> None:
    started = datetime(2026, 9, 19, 10, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    async with db.sessions() as session:
        session.add(RequestLog(**_row(started_at=started)))
        await session.commit()
    async with db.sessions() as session:
        stored = (await session.execute(select(RequestLog))).scalar_one()
    assert stored.started_at == started
    assert stored.started_at.utcoffset() is not None


async def test_each_test_starts_with_an_empty_table(db: Database) -> None:
    async with db.sessions() as session:
        assert (await session.execute(select(RequestLog))).first() is None
        session.add(RequestLog(**_row()))
        await session.commit()


def test_migration_can_be_reversed_and_reapplied(
    migrated_database: Settings, alembic_cfg: Config
) -> None:
    engine = create_engine(build_database_url(migrated_database))
    try:
        command.downgrade(alembic_cfg, "base")
        assert "request_logs" not in inspect(engine).get_table_names()
    finally:
        command.upgrade(alembic_cfg, "head")
    assert "request_logs" in inspect(engine).get_table_names()
    engine.dispose()
