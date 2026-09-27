"""Aggregate request_logs into the statistics returned by GET /metrics.

Every query reads the half-open window [start, end) and runs in the caller's session,
so the router can run them all in one snapshot transaction.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RequestLog
from app.schemas.metrics import (
    EndpointMetrics,
    EndpointTrend,
    LatencyTrend,
    RecentRequest,
    StatusCodeCount,
    Summary,
    TrendBucket,
)


@dataclass(frozen=True, slots=True)
class TimeWindow:
    start: datetime
    end: datetime  # exclusive

    def __post_init__(self) -> None:
        # The database would read a naive time in its own time zone, silently shifting the window.
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Window bounds must be timezone-aware.")
        if self.start >= self.end:
            raise ValueError("Window start must be before its end.")

    @classmethod
    def ending_at(cls, end: datetime, minutes: int) -> "TimeWindow":
        return cls(start=end - timedelta(minutes=minutes), end=end)

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60


# The RequestStats columns, shared by the summary, per-endpoint and trend queries.
# On zero rows, count is 0 and avg and percentile_cont are NULL, which the schema expects.
STATS_COLUMNS = (
    func.count().label("total_requests"),
    func.count().filter(RequestLog.status_code >= 500).label("server_errors"),
    func.count().filter(RequestLog.status_code.between(400, 499)).label("client_errors"),
    func.avg(RequestLog.latency_ms).label("avg_latency_ms"),
    func.percentile_cont(0.95).within_group(RequestLog.latency_ms).label("p95_latency_ms"),
)


EMPTY_STATS: Mapping[str, Any] = {
    "total_requests": 0,
    "server_errors": 0,
    "client_errors": 0,
    "error_rate": None,
    "avg_latency_ms": None,
    "p95_latency_ms": None,
}

# Buckets are aligned to this instant, so boundaries fall on round UTC times (10:00, 10:05)
# and stay put between refreshes. SQL's date_bin and bucket_starts() must both use it.
BUCKET_ORIGIN = datetime(2000, 1, 1, tzinfo=UTC)


def in_window(window: TimeWindow) -> tuple[ColumnElement[bool], ...]:
    return (RequestLog.started_at >= window.start, RequestLog.started_at < window.end)


def stats_fields(row: Row[Any]) -> dict[str, Any]:
    """Turn a row selected with STATS_COLUMNS into RequestStats fields."""
    total = row.total_requests
    return {
        "total_requests": total,
        "server_errors": row.server_errors,
        "client_errors": row.client_errors,
        "error_rate": row.server_errors / total if total else None,
        "avg_latency_ms": row.avg_latency_ms,
        "p95_latency_ms": row.p95_latency_ms,
    }


async def summary(session: AsyncSession, window: TimeWindow) -> Summary:
    # Without GROUP BY an aggregate query always returns one row, even for an empty window.
    row = (await session.execute(select(*STATS_COLUMNS).where(*in_window(window)))).one()
    return Summary.model_validate(
        stats_fields(row) | {"requests_per_minute": row.total_requests / window.minutes}
    )


async def endpoint_metrics(session: AsyncSession, window: TimeWindow) -> list[EndpointMetrics]:
    # A fixed order keeps the dashboard table from reshuffling on every refresh.
    statement = (
        select(RequestLog.method, RequestLog.endpoint, *STATS_COLUMNS)
        .where(*in_window(window))
        .group_by(RequestLog.endpoint, RequestLog.method)
        .order_by(RequestLog.endpoint, RequestLog.method)
    )
    return [
        EndpointMetrics.model_validate(
            stats_fields(row) | {"method": row.method, "endpoint": row.endpoint}
        )
        for row in await session.execute(statement)
    ]


async def status_codes(session: AsyncSession, window: TimeWindow) -> list[StatusCodeCount]:
    # Not labelled "count": a Row is a tuple, so row.count would be tuple.count().
    statement = (
        select(RequestLog.status_code, func.count().label("occurrences"))
        .where(*in_window(window))
        .group_by(RequestLog.status_code)
        .order_by(RequestLog.status_code)
    )
    return [
        StatusCodeCount(status_code=row.status_code, count=row.occurrences)
        for row in await session.execute(statement)
    ]


def bucket_starts(window: TimeWindow, bucket: timedelta) -> list[datetime]:
    """The aligned start of every bucket that overlaps the window, oldest first.

    The first start can be before window.start; fill_buckets clips it.
    """
    if bucket <= timedelta(0):
        raise ValueError("Bucket size must be positive.")
    current = window.start - (window.start - BUCKET_ORIGIN) % bucket
    starts: list[datetime] = []
    while current < window.end:
        starts.append(current)
        current += bucket
    return starts


def fill_buckets(
    window: TimeWindow, bucket: timedelta, rows: Mapping[datetime, Row[Any]]
) -> list[TrendBucket]:
    """One TrendBucket per bucket in the window: stats where SQL found rows, empty elsewhere."""
    starts = bucket_starts(window, bucket)
    # SQL and Python must agree on the buckets; if they drift, fail loudly rather than drop data.
    unknown = rows.keys() - set(starts)
    if unknown:
        raise RuntimeError(f"Database buckets {sorted(unknown)} are not in the window's buckets.")
    return [
        TrendBucket.model_validate(
            {
                **(stats_fields(rows[start]) if start in rows else EMPTY_STATS),
                "start": max(start, window.start),  # edge buckets are clipped to the window
                "end": min(start + bucket, window.end),
            }
        )
        for start in starts
    ]


async def latency_trend(
    session: AsyncSession, window: TimeWindow, bucket: timedelta
) -> LatencyTrend:
    bucket_start = func.date_bin(bucket, RequestLog.started_at, BUCKET_ORIGIN).label("bucket_start")

    # Two queries, because percentiles do not add up: the overall p95 cannot be
    # derived from per-endpoint p95s.
    overall = await session.execute(
        select(bucket_start, *STATS_COLUMNS).where(*in_window(window)).group_by(bucket_start)
    )
    per_endpoint = await session.execute(
        select(RequestLog.method, RequestLog.endpoint, bucket_start, *STATS_COLUMNS)
        .where(*in_window(window))
        .group_by(RequestLog.endpoint, RequestLog.method, bucket_start)
        .order_by(RequestLog.endpoint, RequestLog.method)
    )

    # Dicts keep insertion order, so endpoints stay in the same order as endpoint_metrics.
    endpoint_rows: dict[tuple[str, str], dict[datetime, Row[Any]]] = {}
    for row in per_endpoint:
        endpoint_rows.setdefault((row.endpoint, row.method), {})[row.bucket_start] = row

    return LatencyTrend(
        overall=fill_buckets(window, bucket, {row.bucket_start: row for row in overall}),
        by_endpoint=[
            EndpointTrend(
                method=method, endpoint=endpoint, buckets=fill_buckets(window, bucket, rows)
            )
            for (endpoint, method), rows in endpoint_rows.items()
        ],
    )


async def recent_requests(
    session: AsyncSession, window: TimeWindow, limit: int
) -> list[RecentRequest]:
    # The started_at index is read backwards and the scan stops after `limit` rows.
    statement = (
        select(RequestLog)
        .where(*in_window(window))
        .order_by(RequestLog.started_at.desc(), RequestLog.id.desc())
        .limit(limit)
    )
    return [
        RecentRequest(
            id=log.id,
            method=log.method,
            endpoint=log.endpoint,
            status_code=log.status_code,
            latency_ms=log.latency_ms,
            # PostgreSQL returns times in the session's time zone; the contract is UTC.
            started_at=log.started_at.astimezone(UTC),
        )
        for log in await session.scalars(statement)
    ]
