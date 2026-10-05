"""Build the AI provider's input from query results, without a database."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.schemas.metrics import EndpointMetrics, StatusCodeCount, Summary
from app.services.analysis.input import (
    EMPTY_HALF,
    HalfStats,
    build_analysis_input,
    split_in_half,
)
from app.services.metrics import TimeWindow

END = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
WINDOW = TimeWindow.ending_at(END, 60)


def stats(**overrides: Any) -> dict[str, Any]:
    return {
        "total_requests": 100,
        "server_errors": 4,
        "client_errors": 2,
        "error_rate": 0.04,
        "avg_latency_ms": 100.0,
        "p95_latency_ms": 200.0,
    } | overrides


def endpoint(method: str = "GET", path: str = "/demo/users", **overrides: Any) -> EndpointMetrics:
    return EndpointMetrics.model_validate(stats(**overrides) | {"method": method, "endpoint": path})


def build(**overrides: Any):
    arguments = {
        "window": WINDOW,
        "totals": Summary.model_validate(stats(requests_per_minute=100 / 60)),
        "endpoints": [endpoint()],
        "first_half": [endpoint(total_requests=40)],
        "second_half": [endpoint(total_requests=60)],
        "codes": [StatusCodeCount(status_code=200, count=94)],
    } | overrides
    return build_analysis_input(**arguments)


def test_the_halves_touch_and_cover_the_window() -> None:
    early, late = split_in_half(WINDOW)
    assert (early.start, early.end, late.start, late.end) == (
        WINDOW.start,
        END - timedelta(minutes=30),
        END - timedelta(minutes=30),
        END,
    )


def test_an_odd_window_is_split_exactly_in_the_middle() -> None:
    early, late = split_in_half(TimeWindow.ending_at(END, 5))
    assert early.end == late.start == END - timedelta(minutes=2, seconds=30)


def test_endpoints_are_named_by_method_and_route() -> None:
    result = build(endpoints=[endpoint("POST", "/demo/orders"), endpoint("GET", "/demo/orders")])
    assert [e.endpoint for e in result.endpoints] == ["POST /demo/orders", "GET /demo/orders"]
    assert result.endpoint_names() == {"POST /demo/orders", "GET /demo/orders"}


def test_numbers_are_rounded_for_the_model_and_nulls_stay_null() -> None:
    result = build(
        endpoints=[endpoint(avg_latency_ms=123.456, p95_latency_ms=None, error_rate=1 / 24)]
    )
    summary = result.summary
    assert (summary.requests_per_minute, summary.error_rate) == (1.7, 0.04)
    only = result.endpoints[0]
    assert (only.avg_latency_ms, only.p95_latency_ms, only.error_rate) == (123.5, None, 0.042)


def test_each_endpoint_gets_its_own_half_numbers() -> None:
    result = build(
        endpoints=[endpoint("GET", "/demo/orders"), endpoint("POST", "/demo/orders")],
        first_half=[
            endpoint("POST", "/demo/orders", total_requests=7, p95_latency_ms=301.06),
            endpoint("GET", "/demo/orders", total_requests=3, error_rate=0.3333),
        ],
        second_half=[endpoint("GET", "/demo/orders", total_requests=5)],
    )
    get, post = result.endpoints
    assert get.first_half == HalfStats(total_requests=3, error_rate=0.333, p95_latency_ms=200.0)
    assert post.first_half == HalfStats(total_requests=7, error_rate=0.04, p95_latency_ms=301.1)
    assert get.second_half.total_requests == 5


def test_an_endpoint_with_no_requests_in_one_half_shows_an_empty_half() -> None:
    result = build(second_half=[])
    assert result.endpoints[0].second_half == EMPTY_HALF
    assert EMPTY_HALF.error_rate is EMPTY_HALF.p95_latency_ms is None


def test_window_and_status_codes_are_passed_through() -> None:
    result = build()
    assert (result.window.start, result.window.end, result.window.minutes) == (
        WINDOW.start,
        END,
        60,
    )
    assert [code.status_code for code in result.status_codes] == [200]


def test_the_input_for_every_demo_endpoint_stays_small() -> None:
    """About 4 characters per token: six endpoints stay well under 1,000 tokens."""
    routes = [
        ("GET", "/demo/users"),
        ("GET", "/demo/products"),
        ("GET", "/demo/orders"),
        ("POST", "/demo/orders"),
        ("GET", "/demo/search"),
        ("GET", "/demo/reports"),
    ]
    every = [endpoint(m, p, avg_latency_ms=1234.5678) for m, p in routes]
    codes = [StatusCodeCount(status_code=s, count=10) for s in (200, 201, 422, 500, 503, 504)]
    result = build(endpoints=every, first_half=every, second_half=every, codes=codes)
    assert len(json.dumps(result.model_dump(mode="json"))) < 4000


def test_the_input_cannot_be_changed_after_it_is_built() -> None:
    with pytest.raises(ValueError):
        build().summary.total_requests = 0  # type: ignore[misc]
