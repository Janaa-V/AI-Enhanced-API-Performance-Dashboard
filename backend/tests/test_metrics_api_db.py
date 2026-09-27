"""GET /metrics end to end: real app, real startup, real PostgreSQL, a fixed clock."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.api.dependencies import get_clock
from app.database import Database
from app.models import RequestLog

pytestmark = pytest.mark.integration

END = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)


def log(
    minutes_ago: float,
    *,
    method: str = "GET",
    endpoint: str = "/demo/users",
    status: int = 200,
    latency: float = 40.0,
) -> RequestLog:
    return RequestLog(
        method=method,
        endpoint=endpoint,
        status_code=status,
        latency_ms=latency,
        started_at=END - timedelta(minutes=minutes_ago),
    )


async def add(db: Database, *logs: RequestLog) -> None:
    async with db.sessions() as session:
        session.add_all(logs)
        await session.commit()


@pytest.fixture
def metrics_client(running_app):
    """The real app with the clock fixed at END."""

    @asynccontextmanager
    async def start(**overrides: object):
        async with running_app(**overrides) as (application, client):
            application.dependency_overrides[get_clock] = lambda: lambda: END
            yield client

    return start


async def test_the_response_combines_every_part_for_the_same_window(
    db: Database, metrics_client
) -> None:
    await add(
        db,
        log(10),
        log(20, method="POST", endpoint="/demo/orders", status=503, latency=300),
        log(70, status=422),  # outside the 60-minute window
    )
    async with metrics_client() as client:
        response = await client.get("/metrics?window_minutes=60&bucket_minutes=5")
    assert response.status_code == 200
    body = response.json()
    assert body["window"] == {
        "start": "2026-09-27T09:00:00Z",
        "end": "2026-09-27T10:00:00Z",
        "window_minutes": 60,
        "bucket_minutes": 5,
    }
    assert (body["summary"]["total_requests"], body["summary"]["error_rate"]) == (2, 0.5)
    assert [(e["endpoint"], e["method"]) for e in body["endpoints"]] == [
        ("/demo/orders", "POST"),
        ("/demo/users", "GET"),
    ]
    assert body["status_codes"] == [
        {"status_code": 200, "count": 1},
        {"status_code": 503, "count": 1},
    ]
    assert len(body["latency_trend"]["overall"]) == 12
    assert [r["endpoint"] for r in body["recent_requests"]] == ["/demo/users", "/demo/orders"]


async def test_defaults_come_from_settings_and_the_documented_values(
    db: Database, metrics_client
) -> None:
    await add(db, *(log(1 + i * 0.5) for i in range(25)))
    async with metrics_client(metrics_window_minutes=30) as client:
        body = (await client.get("/metrics")).json()
    assert (body["window"]["window_minutes"], body["window"]["bucket_minutes"]) == (30, 5)
    assert len(body["recent_requests"]) == 20


async def test_the_largest_allowed_bucket_count_is_accepted(db: Database, metrics_client) -> None:
    async with metrics_client() as client:
        response = await client.get("/metrics?window_minutes=1440&bucket_minutes=5")
    assert response.status_code == 200
    assert len(response.json()["latency_trend"]["overall"]) == 288


async def test_metrics_requests_are_not_recorded(db: Database, metrics_client) -> None:
    async with metrics_client() as client:
        assert (await client.get("/metrics")).status_code == 200
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(RequestLog)) == 0


async def test_the_route_and_its_schema_are_published_for_client_generation(
    db: Database, metrics_client
) -> None:
    async with metrics_client() as client:
        spec = (await client.get("/openapi.json")).json()
    responses = spec["paths"]["/metrics"]["get"]["responses"]
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/MetricsResponse"
    )
    assert "503" in responses
    assert "MetricsResponse" in spec["components"]["schemas"]
