"""Verify the /metrics response contract that the frontend types are generated from."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.metrics import (
    MetricsResponse,
    MetricsWindow,
    RecentRequest,
    RequestStats,
    StatusCodeCount,
)

END = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)
START = END - timedelta(minutes=60)

EMPTY_STATS: dict[str, Any] = {
    "total_requests": 0,
    "server_errors": 0,
    "client_errors": 0,
    "error_rate": None,
    "avg_latency_ms": None,
    "p95_latency_ms": None,
}


def window(**overrides: Any) -> dict[str, Any]:
    return {"start": START, "end": END, "window_minutes": 60, "bucket_minutes": 5} | overrides


def test_an_empty_window_is_valid_with_zero_counts_nulls_and_empty_lists() -> None:
    response = MetricsResponse.model_validate(
        {
            "window": window(),
            "summary": EMPTY_STATS | {"requests_per_minute": 0},
            "endpoints": [],
            "status_codes": [],
            "latency_trend": {
                "overall": [EMPTY_STATS | {"start": START, "end": END}],
                "by_endpoint": [],
            },
            "recent_requests": [],
        }
    )
    assert response.summary.avg_latency_ms is None
    assert response.latency_trend.overall[0].total_requests == 0


@pytest.mark.parametrize("field", ["error_rate", "avg_latency_ms", "p95_latency_ms"])
def test_nullable_stats_are_still_required(field: str) -> None:
    """A missing value would be undefined in TypeScript; the contract always sends null."""
    stats = {k: v for k, v in EMPTY_STATS.items() if k != field}
    with pytest.raises(ValidationError):
        RequestStats.model_validate(stats)
    assert field in RequestStats.model_json_schema()["required"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("error_rate", 1.01), ("error_rate", -0.1), ("server_errors", -1), ("p95_latency_ms", -1)],
)
def test_stats_reject_impossible_values(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        RequestStats.model_validate(EMPTY_STATS | {field: value})


def test_timestamps_without_a_timezone_are_rejected() -> None:
    with pytest.raises(ValidationError):
        MetricsWindow.model_validate(window(start=START.replace(tzinfo=None)))


def test_utc_timestamps_serialize_as_iso_8601_with_z() -> None:
    dumped = MetricsWindow.model_validate(window()).model_dump(mode="json")
    assert dumped["start"] == "2026-09-27T09:00:00Z"
    assert dumped["end"] == "2026-09-27T10:00:00Z"


@pytest.mark.parametrize(
    "overrides", [{"window_minutes": 0}, {"window_minutes": 1441}, {"bucket_minutes": 61}]
)
def test_window_sizes_are_bounded(overrides: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        MetricsWindow.model_validate(window(**overrides))


def test_status_codes_list_only_statuses_that_occurred() -> None:
    with pytest.raises(ValidationError):
        StatusCodeCount(status_code=200, count=0)


def test_recent_request_rejects_a_status_outside_http_range() -> None:
    with pytest.raises(ValidationError):
        RecentRequest(
            id=1,
            method="GET",
            endpoint="/demo/users",
            status_code=600,
            latency_ms=10,
            started_at=END,
        )
