"""Verify every /metrics query against real PostgreSQL."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.database import Database
from app.models import RequestLog
from app.services.metrics import (
    TimeWindow,
    begin_snapshot,
    collect_metrics,
    endpoint_metrics,
    latency_trend,
    recent_requests,
    status_codes,
    summary,
)

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


# Latency trend: a window of 09:02:37 to 10:02:37 in 5-minute buckets, 13 in all.
TREND_WINDOW = TimeWindow(
    start=datetime(2026, 9, 27, 9, 2, 37, tzinfo=UTC),
    end=datetime(2026, 9, 27, 10, 2, 37, tzinfo=UTC),
)
FIVE_MINUTES = timedelta(minutes=5)


def clock(minute: int, second: int = 0, microsecond: int = 0) -> datetime:
    return datetime(2026, 9, 27, 9, 0, tzinfo=UTC) + timedelta(
        minutes=minute, seconds=second, microseconds=microsecond
    )


async def test_rows_on_bucket_edges_land_where_python_expects(db: Database) -> None:
    await add(
        db,
        log(at=clock(4, 59, 999_999), latency=10),  # last instant of the clipped first bucket
        log(at=clock(5), latency=20),  # first instant of the second bucket
        log(at=clock(60), latency=30),  # 10:00, the clipped last bucket
    )
    async with db.sessions() as session:
        trend = await latency_trend(session, TREND_WINDOW, FIVE_MINUTES)
    buckets = trend.overall
    assert len(buckets) == 13
    assert (buckets[0].start, buckets[0].end) == (TREND_WINDOW.start, clock(5))
    assert (buckets[-1].start, buckets[-1].end) == (clock(60), TREND_WINDOW.end)
    assert [
        (b.total_requests, b.avg_latency_ms) for b in (buckets[0], buckets[1], buckets[-1])
    ] == [
        (1, 10),
        (1, 20),
        (1, 30),
    ]
    assert (buckets[2].total_requests, buckets[2].p95_latency_ms) == (0, None)


async def test_the_overall_p95_is_computed_from_rows_not_from_endpoint_p95s(db: Database) -> None:
    # 20 rows in one bucket: overall p95 is between 108 and 109 at position 18.05 (108.05);
    # the reports endpoint alone has p95 108.55, and users far less.
    await add(
        db,
        *(log(at=clock(10), endpoint="/demo/users", latency=ms) for ms in range(1, 11)),
        *(log(at=clock(10), endpoint="/demo/reports", latency=ms) for ms in range(100, 110)),
    )
    async with db.sessions() as session:
        trend = await latency_trend(session, TREND_WINDOW, FIVE_MINUTES)
    bucket = trend.overall[2]
    assert bucket.start == clock(10)
    assert bucket.p95_latency_ms == pytest.approx(108.05)
    reports = trend.by_endpoint[0]
    assert reports.endpoint == "/demo/reports"
    assert reports.buckets[2].p95_latency_ms == pytest.approx(108.55)


async def test_each_endpoint_gets_every_bucket_in_the_table_order(db: Database) -> None:
    await add(
        db,
        log(at=clock(10), endpoint="/demo/users"),
        log(at=clock(20), method="POST", endpoint="/demo/orders", status=201),
        log(at=clock(30), endpoint="/demo/orders"),
    )
    async with db.sessions() as session:
        trend = await latency_trend(session, TREND_WINDOW, FIVE_MINUTES)
        table = await endpoint_metrics(session, TREND_WINDOW)
    assert [(t.endpoint, t.method) for t in trend.by_endpoint] == [
        (e.endpoint, e.method) for e in table
    ]
    assert all(len(t.buckets) == 13 for t in trend.by_endpoint)
    post_orders = trend.by_endpoint[1]
    assert [b.total_requests for b in post_orders.buckets].count(1) == 1


async def test_an_empty_window_has_every_bucket_and_no_endpoints(db: Database) -> None:
    async with db.sessions() as session:
        trend = await latency_trend(session, TREND_WINDOW, FIVE_MINUTES)
    assert len(trend.overall) == 13
    assert all(b.total_requests == 0 and b.avg_latency_ms is None for b in trend.overall)
    assert trend.by_endpoint == []


async def test_recent_requests_are_newest_first_with_id_breaking_ties(db: Database) -> None:
    await add(
        db,
        log(at=WINDOW.start - TICK, endpoint="/demo/outside-before"),
        log(at=MIDDLE, endpoint="/demo/first"),
        log(at=MIDDLE, endpoint="/demo/second"),  # same time, higher id
        log(at=END - TICK, endpoint="/demo/newest"),
        log(at=END, endpoint="/demo/outside-after"),
    )
    async with db.sessions() as session:
        recent = await recent_requests(session, WINDOW, limit=10)
        limited = await recent_requests(session, WINDOW, limit=2)
    assert [r.endpoint for r in recent] == ["/demo/newest", "/demo/second", "/demo/first"]
    assert [r.endpoint for r in limited] == ["/demo/newest", "/demo/second"]


async def test_recent_request_times_are_utc_whatever_the_database_time_zone(db: Database) -> None:
    await add(db, log(at=MIDDLE))
    async with db.sessions() as session:
        await session.execute(text("SET TIME ZONE 'Asia/Kolkata'"))
        (recent,) = await recent_requests(session, WINDOW, limit=1)
    assert recent.model_dump(mode="json")["started_at"] == "2026-09-27T09:30:00Z"


SNAPSHOT_SETTINGS = text(
    "SELECT current_setting('transaction_isolation'),"
    " current_setting('transaction_read_only'),"
    " current_setting('statement_timeout')"
)


async def test_the_snapshot_is_repeatable_read_read_only_and_time_limited(db: Database) -> None:
    async with db.sessions() as session:
        await begin_snapshot(session)
        settings = (await session.execute(SNAPSHOT_SETTINGS)).one()
    assert tuple(settings) == ("repeatable read", "on", "5s")


async def test_a_row_saved_during_the_snapshot_is_not_seen_by_later_queries(db: Database) -> None:
    await add(db, log())
    async with db.sessions() as session:
        await begin_snapshot(session)
        before = await summary(session, WINDOW)
        await add(db, log())  # committed by another connection, as the recorder would
        after = await summary(session, WINDOW)
        table = await endpoint_metrics(session, WINDOW)
    assert before.total_requests == after.total_requests == table[0].total_requests == 1


async def test_collect_metrics_runs_every_query_inside_the_snapshot(db: Database) -> None:
    await add(db, log())
    async with db.sessions() as session:
        response = await collect_metrics(
            session, end=END, window_minutes=60, bucket_minutes=5, recent_limit=5
        )
        # Still inside the transaction collect_metrics used.
        settings = (await session.execute(SNAPSHOT_SETTINGS)).one()
    assert tuple(settings) == ("repeatable read", "on", "5s")
    assert response.summary.total_requests == len(response.recent_requests) == 1
