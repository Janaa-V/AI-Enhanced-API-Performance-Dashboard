"""End to end: real app, real startup, real PostgreSQL, the keyless fake provider."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.database import Database
from app.models import RequestLog

pytestmark = pytest.mark.integration

FAKE = {"ai_provider": "fake", "ai_api_key": ""}


async def add_recent_requests(db: Database, count: int = 25) -> None:
    now = datetime.now(UTC)
    async with db.sessions() as session:
        session.add_all(
            RequestLog(
                method="GET",
                endpoint="/demo/reports",
                status_code=200,
                latency_ms=900.0,
                started_at=now - timedelta(minutes=5),
            )
            for _ in range(count)
        )
        await session.commit()


async def row_count(db: Database) -> int:
    async with db.sessions() as session:
        return await session.scalar(select(func.count()).select_from(RequestLog)) or 0


async def test_an_analysis_then_the_same_answer_from_the_cache(running_app, db: Database) -> None:
    await add_recent_requests(db)
    async with running_app(**FAKE) as (_, client):
        first = await client.post("/analyze", json={"window_minutes": 60})
        second = await client.post("/analyze", json={"window_minutes": 60})
    assert first.status_code == second.status_code == 200
    body = first.json()
    assert (body["status"], body["provider"], body["cached"]) == ("ok", "fake", False)
    assert body["analysis"]["observations"][0]["endpoint"] == "GET /demo/reports"
    assert second.json()["cached"] is True
    assert await row_count(db) == 25  # /analyze itself is never recorded


async def test_a_quiet_window_is_no_data(running_app, db: Database) -> None:
    await add_recent_requests(db, count=3)
    async with running_app(**FAKE) as (_, client):
        response = await client.post("/analyze")
    assert response.status_code == 200
    assert (response.json()["status"], response.json()["analysis"]) == ("no_data", None)


async def test_the_quota_stops_the_next_real_call(running_app, db: Database) -> None:
    await add_recent_requests(db)
    async with running_app(**FAKE, ai_quota_per_hour=1, ai_cache_seconds=0) as (_, client):
        allowed = await client.post("/analyze")
        refused = await client.post("/analyze")
    assert allowed.status_code == 200
    assert refused.status_code == 429
    assert 3590 <= int(refused.headers["retry-after"]) <= 3600


async def test_without_a_provider_the_route_says_so(running_app, db: Database) -> None:
    async with running_app(ai_provider="disabled") as (_, client):
        response = await client.post("/analyze")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_disabled"
