"""End to end: real app, real startup, real PostgreSQL. Requests must leave the right rows."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from sqlalchemy import select

from app.config import Settings
from app.database import Database
from app.main import create_app
from app.models import RequestLog
from app.services.request_recorder import RequestRecorder

pytestmark = pytest.mark.integration

QUIET = {"simulation_latency_scale": 0, "simulation_failure_scale": 0}
ORDER = {"user_id": 1, "items": [{"product_id": 1, "quantity": 2}]}
ORIGIN = "http://localhost:5173"


@pytest.fixture
def running_app(migrated_database: Settings, monkeypatch: pytest.MonkeyPatch):
    """Start the real app (lifespan included) against the test database; yield (app, client)."""

    @asynccontextmanager
    async def start(**overrides: float):
        settings = migrated_database.model_copy(update=overrides)
        monkeypatch.setattr("app.main.get_settings", lambda: settings)
        application = create_app()
        async with application.router.lifespan_context(application):
            transport = httpx2.ASGITransport(app=application)
            async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
                yield application, client

    return start


async def all_rows(db: Database) -> list[RequestLog]:
    async with db.sessions() as session:
        return list((await session.execute(select(RequestLog).order_by(RequestLog.id))).scalars())


ROUTES = [
    ("GET", "/demo/users", None, 200, "/demo/users"),
    ("GET", "/demo/products", None, 200, "/demo/products"),
    ("GET", "/demo/orders", None, 200, "/demo/orders"),
    ("GET", "/demo/search?q=lap", None, 200, "/demo/search"),
    ("GET", "/demo/reports", None, 200, "/demo/reports"),
    ("POST", "/demo/orders", ORDER, 201, "/demo/orders"),
]


@pytest.mark.parametrize(
    ("method", "url", "body", "status", "endpoint"),
    ROUTES,
    ids=["users", "products", "orders", "search", "reports", "create-order"],
)
async def test_each_demo_call_adds_exactly_one_correct_row(
    running_app, db: Database, method: str, url: str, body: dict | None, status: int, endpoint: str
) -> None:
    before = datetime.now(UTC) - timedelta(seconds=1)
    async with running_app(**QUIET) as (_, client):
        response = await client.request(method, url, json=body)
    assert response.status_code == status
    (row,) = await all_rows(db)
    assert (row.method, row.endpoint, row.status_code) == (method, endpoint, status)
    assert row.latency_ms >= 0
    assert before <= row.started_at <= datetime.now(UTC)  # a real, timezone-aware UTC time


@pytest.mark.parametrize("path", ["/health", "/docs", "/openapi.json", "/demo/nothing"])
async def test_monitoring_routes_and_unknown_paths_add_no_rows(
    running_app, db: Database, path: str
) -> None:
    async with running_app(**QUIET) as (_, client):
        await client.get(path)
    assert await all_rows(db) == []


async def test_a_browser_preflight_adds_no_row(running_app, db: Database) -> None:
    async with running_app(**QUIET) as (_, client):
        response = await client.options(
            "/demo/orders",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert response.status_code == 200
    assert await all_rows(db) == []


async def test_simulated_failures_are_recorded_with_the_status_the_client_saw(
    running_app, db: Database
) -> None:
    async with running_app(simulation_latency_scale=0, simulation_failure_scale=100) as (_, client):
        responses = [await client.get("/demo/reports"), await client.get("/demo/users")]
    rows = await all_rows(db)
    assert [row.status_code for row in rows] == [r.status_code for r in responses]
    assert all(row.status_code >= 500 for row in rows)


async def test_forty_concurrent_requests_leave_exactly_forty_rows(
    running_app, db: Database
) -> None:
    async with running_app(**QUIET) as (_, client):
        paths = ["/demo/users", "/demo/products", "/demo/orders", "/demo/reports"]
        await asyncio.gather(*(client.get(paths[i % 4]) for i in range(40)))
    rows = await all_rows(db)
    assert len(rows) == 40
    assert {row.endpoint for row in rows} == set(paths)
    assert all(sum(row.endpoint == p for row in rows) == 10 for p in paths)


async def test_the_recorded_latency_includes_the_simulated_delay(running_app, db: Database) -> None:
    async with running_app(simulation_latency_scale=1, simulation_failure_scale=0) as (_, client):
        started = time.perf_counter()
        await client.post("/demo/orders", json=ORDER)
        observed_ms = (time.perf_counter() - started) * 1000
    (row,) = await all_rows(db)
    assert 100 <= row.latency_ms  # creating an order waits at least 100 ms
    assert row.latency_ms <= observed_ms  # and the client waited at least that long


async def test_a_database_failure_never_changes_the_response(
    running_app, db: Database, caplog: pytest.LogCaptureFixture
) -> None:
    dead = Database(Settings(_env_file=None, db_password="unused", db_port=1))
    try:
        async with running_app(**QUIET) as (application, client):
            healthy = await client.get("/demo/users")
            application.state.recorder = RequestRecorder(dead.sessions, timeout_seconds=1)
            with caplog.at_level(logging.WARNING):
                broken = await client.get("/demo/users")
    finally:
        await dead.close()
    assert broken.status_code == healthy.status_code == 200
    assert broken.json() == healthy.json()
    assert "Could not record request GET /demo/users" in caplog.text
    assert len(await all_rows(db)) == 1  # only the healthy request was saved
