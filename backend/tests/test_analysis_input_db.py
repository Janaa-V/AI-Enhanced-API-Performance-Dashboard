"""Collect the AI provider's input from real PostgreSQL."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.database import Database
from app.models import RequestLog
from app.services.analysis.input import collect_analysis_input

pytestmark = pytest.mark.integration

END = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
START = END - timedelta(minutes=60)
MIDDLE = END - timedelta(minutes=30)
TICK = timedelta(microseconds=1)  # PostgreSQL's timestamp resolution


def log(at: datetime, *, status: int = 200, latency: float = 50.0) -> RequestLog:
    return RequestLog(
        method="GET",
        endpoint="/demo/reports",
        status_code=status,
        latency_ms=latency,
        started_at=at,
    )


async def add(db: Database, *logs: RequestLog) -> None:
    async with db.sessions() as session:
        session.add_all(logs)
        await session.commit()


async def test_every_row_lands_in_exactly_one_half(db: Database) -> None:
    await add(
        db,
        log(START - TICK),  # before the window
        log(START),  # first half
        log(MIDDLE - TICK),  # first half
        log(MIDDLE, status=504, latency=4000),  # the middle belongs to the second half
        log(END - TICK, latency=3000),  # second half
        log(END),  # after the window
    )
    async with db.sessions() as session:
        result = await collect_analysis_input(session, end=END, window_minutes=60)
    [reports] = result.endpoints
    assert reports.endpoint == "GET /demo/reports"
    assert reports.total_requests == result.summary.total_requests == 4
    assert reports.first_half.total_requests == reports.second_half.total_requests == 2
    assert reports.first_half.error_rate == 0 and reports.second_half.error_rate == 0.5
    assert reports.second_half.p95_latency_ms == 3950.0  # interpolated between 3000 and 4000
    assert [(c.status_code, c.count) for c in result.status_codes] == [(200, 3), (504, 1)]


async def test_an_empty_window_gives_zeros_and_no_endpoints(db: Database) -> None:
    async with db.sessions() as session:
        result = await collect_analysis_input(session, end=END, window_minutes=60)
    assert result.summary.total_requests == 0
    assert result.summary.error_rate is None
    assert result.endpoints == result.status_codes == []


async def test_every_query_runs_inside_one_read_only_snapshot(db: Database) -> None:
    await add(db, log(MIDDLE))
    async with db.sessions() as session:
        await collect_analysis_input(session, end=END, window_minutes=60)
        # Still inside the transaction collect_analysis_input used.
        settings = await session.execute(
            text(
                "SELECT current_setting('transaction_isolation'),"
                " current_setting('transaction_read_only')"
            )
        )
    assert tuple(settings.one()) == ("repeatable read", "on")
