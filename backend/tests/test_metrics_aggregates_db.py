"""Verify the summary, per-endpoint and status-code aggregates against real PostgreSQL."""

from datetime import UTC, datetime, timedelta

import pytest

from app.database import Database
from app.models import RequestLog
from app.services.metrics import TimeWindow, endpoint_metrics, status_codes, summary

pytestmark = pytest.mark.integration

END = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)
WINDOW = TimeWindow.ending_at(END, 60)
MIDDLE = END - timedelta(minutes=30)
TICK = timedelta(microseconds=1)  # PostgreSQL's timestamp resolution


def log(
    *,
    at: datetime = MIDDLE,
    method: str = "GET",
    endpoint: str = "/demo/users",
    status: int = 200,
    latency: float = 50.0,
) -> RequestLog:
    return RequestLog(
        method=method, endpoint=endpoint, status_code=status, latency_ms=latency, started_at=at
    )


async def add(db: Database, *logs: RequestLog) -> None:
    async with db.sessions() as session:
        session.add_all(logs)
        await session.commit()


async def test_an_empty_window_has_zero_counts_nulls_and_empty_lists(db: Database) -> None:
    await add(db, log(at=WINDOW.start - TICK), log(at=END))  # both just outside
    async with db.sessions() as session:
        result = await summary(session, WINDOW)
        assert await endpoint_metrics(session, WINDOW) == []
        assert await status_codes(session, WINDOW) == []
    assert result.total_requests == result.server_errors == result.client_errors == 0
    assert result.error_rate is result.avg_latency_ms is result.p95_latency_ms is None
    assert result.requests_per_minute == 0


async def test_the_window_includes_its_start_and_excludes_its_end(db: Database) -> None:
    await add(
        db,
        log(at=WINDOW.start - TICK, latency=1),
        log(at=WINDOW.start, latency=10),
        log(at=END - TICK, latency=20),
        log(at=END, latency=1000),
    )
    async with db.sessions() as session:
        result = await summary(session, WINDOW)
    assert result.total_requests == 2
    assert result.avg_latency_ms == 15


async def test_only_5xx_counts_towards_the_error_rate(db: Database) -> None:
    statuses = [200, 200, 200, 201, 404, 422, 500, 504]
    await add(db, *(log(status=status) for status in statuses))
    async with db.sessions() as session:
        result = await summary(session, WINDOW)
    assert (result.total_requests, result.server_errors, result.client_errors) == (8, 2, 2)
    assert result.error_rate == 0.25


async def test_p95_is_interpolated_between_the_nearest_latencies(db: Database) -> None:
    # 20 values: p95 sits at position 0.95 * 19 = 18.05, between 19 and 20.
    await add(db, *(log(latency=ms) for ms in range(1, 21)))
    async with db.sessions() as session:
        result = await summary(session, WINDOW)
    assert result.p95_latency_ms == pytest.approx(19.05)
    assert result.avg_latency_ms == pytest.approx(10.5)


async def test_overall_figures_come_from_rows_not_from_averaging_endpoints(db: Database) -> None:
    # Three fast calls and one slow one: the row average is 257.5,
    # while averaging the two endpoint averages would wrongly give 505.
    await add(
        db,
        *(log(endpoint="/demo/users", latency=10) for _ in range(3)),
        log(endpoint="/demo/reports", latency=1000),
    )
    async with db.sessions() as session:
        result = await summary(session, WINDOW)
    assert result.avg_latency_ms == pytest.approx(257.5)


async def test_requests_per_minute_divides_by_the_window_length(db: Database) -> None:
    await add(db, *(log() for _ in range(30)))
    async with db.sessions() as session:
        result = await summary(session, WINDOW)
    assert result.requests_per_minute == 0.5


async def test_endpoints_are_keyed_by_method_and_route_in_a_stable_order(db: Database) -> None:
    await add(
        db,
        log(endpoint="/demo/users", latency=40),
        log(method="POST", endpoint="/demo/orders", status=201, latency=300),
        log(method="POST", endpoint="/demo/orders", status=503, latency=400),
        log(endpoint="/demo/orders", latency=100),
        log(endpoint="/demo/orders", status=422, latency=200),
    )
    async with db.sessions() as session:
        endpoints = await endpoint_metrics(session, WINDOW)
    assert [(e.endpoint, e.method, e.total_requests) for e in endpoints] == [
        ("/demo/orders", "GET", 2),
        ("/demo/orders", "POST", 2),
        ("/demo/users", "GET", 1),
    ]
    get_orders, post_orders, users = endpoints
    assert (get_orders.client_errors, get_orders.error_rate) == (1, 0)
    assert (post_orders.server_errors, post_orders.error_rate) == (1, 0.5)
    assert post_orders.avg_latency_ms == pytest.approx(350)
    assert users.p95_latency_ms == pytest.approx(40)


async def test_status_codes_are_counted_in_ascending_order(db: Database) -> None:
    await add(db, *(log(status=status) for status in [503, 200, 200, 422, 200, 503]))
    async with db.sessions() as session:
        counts = await status_codes(session, WINDOW)
    assert [(c.status_code, c.count) for c in counts] == [(200, 3), (422, 1), (503, 2)]
