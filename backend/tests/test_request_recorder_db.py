"""Verify recording against a real PostgreSQL database."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.database import Database
from app.models import RequestLog
from app.services.request_recorder import RequestRecord, RequestRecorder

pytestmark = pytest.mark.integration


def record(**overrides: object) -> RequestRecord:
    fields: dict[str, object] = {
        "method": "GET",
        "endpoint": "/demo/users",
        "status_code": 200,
        "latency_ms": 42.5,
        "started_at": datetime.now(UTC),
    }
    return RequestRecord(**(fields | overrides))  # type: ignore[arg-type]


async def rows(db: Database) -> list[RequestLog]:
    async with db.sessions() as session:
        return list((await session.execute(select(RequestLog).order_by(RequestLog.id))).scalars())


async def test_a_record_is_saved_with_every_field(db: Database) -> None:
    started = datetime(2026, 9, 19, 10, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    await RequestRecorder(db.sessions).record(
        record(method="POST", status_code=201, started_at=started)
    )
    (row,) = await rows(db)
    assert (row.method, row.endpoint, row.status_code, row.latency_ms) == (
        "POST",
        "/demo/users",
        201,
        42.5,
    )
    assert row.started_at == started  # same instant, whatever the offset


async def test_many_records_saved_at_once_are_all_kept(db: Database) -> None:
    recorder = RequestRecorder(db.sessions)
    await asyncio.gather(*(recorder.record(record(latency_ms=float(i))) for i in range(25)))
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(RequestLog)) == 25
    assert {row.latency_ms for row in await rows(db)} == {float(i) for i in range(25)}


async def test_a_row_the_database_rejects_is_dropped_and_later_records_still_work(
    db: Database, caplog: pytest.LogCaptureFixture
) -> None:
    recorder = RequestRecorder(db.sessions)
    with caplog.at_level(logging.WARNING):
        await recorder.record(record(status_code=20000))  # violates the CHECK constraint
        await recorder.record(record(latency_ms=-1))  # violates the other CHECK constraint
    assert caplog.text.count("Could not record request") == 2
    assert await rows(db) == []
    await recorder.record(record())  # the failures must not poison later saves
    assert len(await rows(db)) == 1


async def test_an_unreachable_database_never_raises(caplog: pytest.LogCaptureFixture) -> None:
    dead = Database(Settings(_env_file=None, db_password="unused", db_port=1))
    try:
        with caplog.at_level(logging.WARNING):
            await RequestRecorder(dead.sessions, timeout_seconds=1).record(record())
    finally:
        await dead.close()
    assert "Could not record request" in caplog.text
