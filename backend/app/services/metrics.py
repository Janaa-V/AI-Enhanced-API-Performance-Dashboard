"""Aggregate request_logs into the statistics returned by GET /metrics.

Every query reads the half-open window [start, end) and runs in the caller's session,
so the router can run them all in one snapshot transaction.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RequestLog
from app.schemas.metrics import EndpointMetrics, StatusCodeCount, Summary


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
