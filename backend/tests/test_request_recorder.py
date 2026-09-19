"""Verify recording is best effort, using a fake session so no database is needed."""

import asyncio
import logging
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import OperationalError

from app.models import RequestLog
from app.services.request_recorder import RequestRecord, RequestRecorder

RECORD = RequestRecord(
    method="POST",
    endpoint="/demo/orders",
    status_code=201,
    latency_ms=123.4,
    started_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
)


class FakeSession:
    """Stands in for an AsyncSession: remembers what happened, or fails on request."""

    def __init__(self, *, commit_error: Exception | None = None, hang: bool = False) -> None:
        self.commit_error = commit_error
        self.hang = hang
        self.added: list[RequestLog] = []
        self.committed = False

    def add(self, row: RequestLog) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        if self.hang:
            await asyncio.Event().wait()  # never finishes
        if self.commit_error:
            raise self.commit_error
        self.committed = True

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


def recorder_for(session: FakeSession, **kwargs: float) -> RequestRecorder:
    return RequestRecorder(lambda: session, **kwargs)  # type: ignore[arg-type,return-value]


async def test_a_record_becomes_one_committed_row_with_every_field() -> None:
    session = FakeSession()
    await recorder_for(session).record(RECORD)
    (row,) = session.added
    assert (row.method, row.endpoint, row.status_code) == ("POST", "/demo/orders", 201)
    assert (row.latency_ms, row.started_at) == (123.4, RECORD.started_at)
    assert session.committed


async def test_a_database_error_is_logged_and_swallowed(caplog: pytest.LogCaptureFixture) -> None:
    error = OperationalError("INSERT", {}, Exception("connection lost"))
    session = FakeSession(commit_error=error)
    with caplog.at_level(logging.WARNING):
        await recorder_for(session).record(RECORD)  # must not raise
    assert not session.committed
    assert "Could not record request POST /demo/orders (status 201)" in caplog.text


async def test_failing_to_open_a_session_is_swallowed(caplog: pytest.LogCaptureFixture) -> None:
    def broken_factory() -> FakeSession:
        raise OSError("no connections available")

    with caplog.at_level(logging.WARNING):
        await RequestRecorder(broken_factory).record(RECORD)  # type: ignore[arg-type]
    assert "Could not record request" in caplog.text


async def test_a_hung_save_is_abandoned_after_the_timeout(caplog: pytest.LogCaptureFixture) -> None:
    session = FakeSession(hang=True)
    with caplog.at_level(logging.WARNING):
        await asyncio.wait_for(recorder_for(session, timeout_seconds=0.05).record(RECORD), 2)
    assert "Could not record request" in caplog.text


async def test_cancellation_is_not_swallowed() -> None:
    """Shutting down cancels in-flight work; recording must let that through."""
    task = asyncio.create_task(
        recorder_for(FakeSession(hang=True), timeout_seconds=30).record(RECORD)
    )
    await asyncio.sleep(0)  # let it start waiting
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_a_record_cannot_be_changed_after_it_is_created() -> None:
    with pytest.raises(AttributeError):
        RECORD.status_code = 500  # type: ignore[misc]


async def test_a_failure_is_one_short_line_with_the_traceback_only_at_debug_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = OperationalError("INSERT INTO request_logs ...", {"p": 1}, Exception("connection lost"))
    with caplog.at_level(logging.DEBUG):
        await recorder_for(FakeSession(commit_error=error)).record(RECORD)
    warning = next(r for r in caplog.records if r.levelno == logging.WARNING)
    assert "\n" not in warning.getMessage()
    assert "OperationalError" in warning.getMessage()
    assert warning.exc_info is None
    assert any(r.levelno == logging.DEBUG and r.exc_info for r in caplog.records)
