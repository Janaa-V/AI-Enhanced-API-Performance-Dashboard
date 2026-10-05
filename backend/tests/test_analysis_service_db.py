"""The analysis service against real PostgreSQL, with a fake provider."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Database
from app.models import RequestLog
from app.schemas.analysis import Analysis
from app.services.analysis.providers import FakeProvider
from app.services.analysis.service import MIN_REQUESTS, analyze

pytestmark = pytest.mark.integration

END = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)


async def add_requests(db: Database, count: int) -> None:
    async with db.sessions() as session:
        session.add_all(
            RequestLog(
                method="GET",
                endpoint="/demo/reports",
                status_code=200,
                latency_ms=900.0,
                started_at=END - timedelta(minutes=10),
            )
            for _ in range(count)
        )
        await session.commit()


class WatchingSession(FakeProvider):
    """Records whether the session still held a transaction when the provider was called."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self.session = session
        self.in_transaction: bool | None = None

    async def complete(self, *, system: str, user: str) -> Analysis:
        self.in_transaction = self.session.in_transaction()
        return await super().complete(system=system, user=user)


async def test_no_connection_is_held_while_the_provider_works(db: Database) -> None:
    await add_requests(db, MIN_REQUESTS)
    async with db.sessions() as session:
        provider = WatchingSession(session)
        result = await analyze(session, provider, clock=lambda: END, window_minutes=60)
    assert provider.in_transaction is False
    assert result.status == "ok"
    assert result.analysis is not None
    assert result.analysis.observations[0].endpoint == "GET /demo/reports"


async def test_a_quiet_window_is_no_data_without_a_provider_call(db: Database) -> None:
    await add_requests(db, MIN_REQUESTS - 1)
    provider = FakeProvider()
    async with db.sessions() as session:
        result = await analyze(session, provider, clock=lambda: END, window_minutes=60)
    assert result.status == "no_data"
    assert provider.calls == []
