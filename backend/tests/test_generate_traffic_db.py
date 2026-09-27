"""The traffic generator against the real app and a real PostgreSQL database."""

import random
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.database import Database
from app.models import RequestLog
from scripts.generate_traffic import BackfillRefused, backfill, run_live

pytestmark = pytest.mark.integration

QUIET = {"simulation_latency_scale": 0, "simulation_failure_scale": 0}
END = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)


async def all_rows(db: Database) -> list[RequestLog]:
    async with db.sessions() as session:
        return list((await session.execute(select(RequestLog))).scalars())


async def test_every_live_request_becomes_exactly_one_row(db: Database, running_app) -> None:
    async with running_app(**QUIET) as (_, client):
        tally = await run_live(
            client,
            duration_seconds=0.5,
            concurrency=3,
            rng=random.Random(1),
            pause_seconds=(0, 0.01),
        )
    rows = await all_rows(db)
    assert tally.total > 20
    assert len(rows) == tally.total
    assert Counter(row.status_code for row in rows) == tally.statuses
    assert {row.endpoint for row in rows} <= {
        "/demo/users",
        "/demo/products",
        "/demo/orders",
        "/demo/search",
        "/demo/reports",
    }


async def test_backfill_writes_the_range_once_and_refuses_to_double_it(
    db: Database, migrated_database: Settings
) -> None:
    written = await backfill(
        db, migrated_database, hours=2, per_minute=10, end=END, rng=random.Random(2)
    )
    async with db.sessions() as session:
        count, earliest, latest = (
            await session.execute(
                select(
                    func.count(), func.min(RequestLog.started_at), func.max(RequestLog.started_at)
                )
            )
        ).one()
    assert written == count == 1200
    assert END - timedelta(hours=2) <= earliest and latest < END

    with pytest.raises(BackfillRefused, match="rows already exist"):
        await backfill(db, migrated_database, hours=1, per_minute=10, end=END, rng=random.Random())
