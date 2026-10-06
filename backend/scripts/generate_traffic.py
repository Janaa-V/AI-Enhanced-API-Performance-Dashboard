"""Generate demo traffic so the dashboard has data to show.

Live mode (the default) sends real HTTP requests to a running server, so every row is
measured by the real middleware. Backfill mode writes past rows straight to the database
so charts have history; those rows are synthetic (drawn from the simulation profiles),
not measured.

    uv run python -m scripts.generate_traffic --duration 300 --concurrency 10
    uv run python -m scripts.generate_traffic --backfill-hours 24
    uv run python -m scripts.generate_traffic --backfill-hours 2 --degrade reports

Live traffic follows the server's own settings; to degrade an endpoint live, start the
server with SIMULATION_DEGRADED_ENDPOINT set instead.
"""

import argparse
import asyncio
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import httpx2
from sqlalchemy import func, insert, select

from app.config import Settings, get_settings
from app.database import Database
from app.models import RequestLog
from app.services.simulation import DEFAULT_PROFILES, Simulator


@dataclass(frozen=True, slots=True)
class Route:
    method: str
    endpoint: str  # the route template, as the middleware records it
    profile: str  # key in DEFAULT_PROFILES
    weight: int  # relative share of traffic


ROUTES = (
    Route("GET", "/demo/users", "users", 30),
    Route("GET", "/demo/products", "products", 25),
    Route("GET", "/demo/orders", "orders", 20),
    Route("GET", "/demo/search", "search", 12),
    Route("GET", "/demo/reports", "reports", 5),
    Route("POST", "/demo/orders", "orders_create", 8),
)
# Some orders are invalid on purpose, so client errors (422) appear on the dashboard.
INVALID_ORDER_SHARE = 0.1
SEARCH_TERMS = ("lap", "usb", "mouse", "hub", "stand", "pro")
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def choose_route(rng: random.Random) -> Route:
    return rng.choices(ROUTES, weights=[route.weight for route in ROUTES])[0]


def is_order(route: Route) -> bool:
    return route.method == "POST"


def order_body(rng: random.Random, *, valid: bool) -> dict[str, Any]:
    item = {"product_id": rng.randint(1, 4), "quantity": rng.randint(1, 3)}
    if valid:
        return {"user_id": rng.randint(1, 3), "items": [item]}
    # Mistakes a real client makes: an unknown product, a zero quantity, a typo in a field.
    return rng.choice(
        [
            {"user_id": 1, "items": [{"product_id": 99, "quantity": 1}]},
            {"user_id": 1, "items": [{"product_id": 1, "quantity": 0}]},
            {"user_id": 1, "items": [{"product_id": 1, "qty": 1}]},
        ]
    )


def build_request(route: Route, rng: random.Random) -> tuple[str, dict[str, Any] | None]:
    """The URL path (with query) and JSON body for one request."""
    if route.endpoint == "/demo/search":
        return f"/demo/search?q={rng.choice(SEARCH_TERMS)}", None
    if is_order(route):
        return route.endpoint, order_body(rng, valid=rng.random() >= INVALID_ORDER_SHARE)
    return route.endpoint, None


# Live traffic


@dataclass
class Tally:
    """What the generator saw from the client side."""

    statuses: Counter[int] = field(default_factory=Counter)
    latencies: defaultdict[tuple[str, str], list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    connection_failures: int = 0

    @property
    def total(self) -> int:
        return sum(self.statuses.values())

    def add(self, route: Route, status: int | None, latency_ms: float) -> None:
        if status is None:
            self.connection_failures += 1
            return
        self.statuses[status] += 1
        self.latencies[(route.method, route.endpoint)].append(latency_ms)

    def summary(self) -> str:
        lines = [f"Requests answered: {self.total}"]
        if self.connection_failures:
            lines.append(f"Connection failures: {self.connection_failures}")
        lines.append(
            "By status: " + ", ".join(f"{s}: {n}" for s, n in sorted(self.statuses.items()))
        )
        # Same order as the /metrics endpoint table: by route, then method.
        for method, endpoint in sorted(self.latencies, key=lambda key: (key[1], key[0])):
            values = self.latencies[(method, endpoint)]
            lines.append(
                f"  {method:4} {endpoint:16} {len(values):5} requests, "
                f"client p95 {p95(values):7.1f} ms"
            )
        return "\n".join(lines)


def p95(values: Sequence[float]) -> float:
    """Interpolated like PostgreSQL's percentile_cont, so it is comparable with /metrics."""
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=20, method="inclusive")[-1]


async def run_live(
    client: httpx2.AsyncClient,
    *,
    duration_seconds: float,
    concurrency: int,
    rng: random.Random,
    pause_seconds: tuple[float, float] = (0.05, 0.3),
    clock: Callable[[], float] = time.monotonic,
) -> Tally:
    """Workers send requests until the time is up, pausing briefly like real users."""
    tally = Tally()
    deadline = clock() + duration_seconds

    async def worker() -> None:
        while clock() < deadline:
            route = choose_route(rng)
            path, body = build_request(route, rng)
            started = time.perf_counter()
            try:
                response = await client.request(route.method, path, json=body)
                status: int | None = response.status_code
            except httpx2.TransportError:
                status = None
            tally.add(route, status, (time.perf_counter() - started) * 1000)
            await asyncio.sleep(rng.uniform(*pause_seconds))

    await asyncio.gather(*(worker() for _ in range(concurrency)))
    return tally


def ensure_local(base_url: str, *, allow_remote: bool) -> None:
    """A load generator should never be one typo away from someone else's server."""
    host = urlsplit(base_url).hostname
    if host not in LOCAL_HOSTS and not allow_remote:
        raise SystemExit(
            f"Refusing to send traffic to {host!r}; pass --allow-remote if you mean it."
        )


# Backfill


class BackfillRefused(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Degraded:
    """Rows for this profile at or after `since` use its degraded behaviour."""

    profile: str  # key in DEFAULT_PROFILES
    since: datetime


def synthetic_logs(
    *,
    start: datetime,
    end: datetime,
    per_minute: float,
    rng: random.Random,
    degraded: Degraded | None = None,
) -> list[dict[str, Any]]:
    """Plausible past rows: the same mix and simulation profiles as live traffic.

    With `degraded`, one endpoint gets worse partway through, as a real incident would.
    """
    healthy = Simulator(rng=rng)
    unhealthy = (
        Simulator(rng=rng, degraded=DEFAULT_PROFILES[degraded.profile]) if degraded else healthy
    )
    count = round((end - start).total_seconds() / 60 * per_minute)
    rows = []
    for _ in range(count):
        route = choose_route(rng)
        started_at = start + (end - start) * rng.random()
        if is_order(route) and rng.random() < INVALID_ORDER_SHARE:
            # The real app rejects a bad body before simulating anything, so it is fast.
            status, latency_ms = 422, rng.uniform(1, 5)
        else:
            simulator = unhealthy if degraded and started_at >= degraded.since else healthy
            outcome = simulator.plan(DEFAULT_PROFILES[route.profile])
            status = outcome.failure_status or (201 if is_order(route) else 200)
            latency_ms = outcome.delay_seconds * 1000
        rows.append(
            {
                "method": route.method,
                "endpoint": route.endpoint,
                "status_code": status,
                "latency_ms": latency_ms,
                "started_at": started_at,
            }
        )
    return rows


async def backfill(
    database: Database,
    settings: Settings,
    *,
    hours: int,
    per_minute: float,
    end: datetime,
    rng: random.Random,
    degraded: Degraded | None = None,
) -> int:
    """Write synthetic rows for [end - hours, end); refuses to mix with existing rows."""
    if settings.environment == "production":
        raise BackfillRefused("Backfill writes invented rows; it never runs in production.")
    start = end - timedelta(hours=hours)
    async with database.sessions() as session:
        existing = await session.scalar(
            select(func.count())
            .select_from(RequestLog)
            .where(RequestLog.started_at >= start, RequestLog.started_at < end)
        )
        if existing:
            raise BackfillRefused(
                f"{existing} rows already exist in that range; running twice would double them. "
                "Empty request_logs first or choose fewer hours."
            )
        rows = synthetic_logs(
            start=start, end=end, per_minute=per_minute, rng=rng, degraded=degraded
        )
        for chunk_start in range(0, len(rows), 5000):
            await session.execute(insert(RequestLog), rows[chunk_start : chunk_start + 5000])
        await session.commit()
    return len(rows)


# Command line


def bounded(low: float, high: float, kind: type = int) -> Callable[[str], Any]:
    def parse(text: str) -> Any:
        value = kind(text)
        if not low <= value <= high:
            raise argparse.ArgumentTypeError(f"must be between {low} and {high}")
        return value

    return parse


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--duration", type=bounded(1, 3600), default=60, help="seconds (live)")
    parser.add_argument("--concurrency", type=bounded(1, 50), default=5, help="workers (live)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="server (live)")
    parser.add_argument("--allow-remote", action="store_true", help="allow a non-local server")
    parser.add_argument(
        "--backfill-hours",
        type=bounded(1, 24),
        help="write synthetic history instead of live traffic",
    )
    parser.add_argument(
        "--per-minute", type=bounded(1, 600, float), default=20, help="backfill rows per minute"
    )
    parser.add_argument(
        "--degrade",
        choices=sorted(DEFAULT_PROFILES),
        help="make this endpoint slow and flaky near the end of the backfill",
    )
    parser.add_argument(
        "--degrade-minutes",
        type=bounded(1, 1440),
        default=30,
        help="how many of the most recent minutes are degraded (backfill)",
    )
    parser.add_argument("--seed", type=int, help="repeatable randomness")
    args = parser.parse_args(argv)
    if args.degrade and not args.backfill_hours:
        parser.error(
            "--degrade only applies to --backfill-hours; for live traffic, start the server "
            "with SIMULATION_DEGRADED_ENDPOINT set"
        )
    return args


async def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    # Demo traffic needs variety, not cryptographic randomness.
    rng = random.Random(args.seed)  # noqa: S311

    if args.backfill_hours:
        settings = get_settings()
        database = Database(settings)
        end = datetime.now(UTC)
        degraded = (
            Degraded(args.degrade, since=end - timedelta(minutes=args.degrade_minutes))
            if args.degrade
            else None
        )
        try:
            written = await backfill(
                database,
                settings,
                hours=args.backfill_hours,
                per_minute=args.per_minute,
                end=end,
                rng=rng,
                degraded=degraded,
            )
        except BackfillRefused as refusal:
            raise SystemExit(f"Backfill refused: {refusal}") from None
        finally:
            await database.close()
        print(
            f"Wrote {written} synthetic rows covering the last {args.backfill_hours} hours "
            f"of database {settings.db_name!r}. They are invented, not measured."
        )
        if degraded:
            print(f"{args.degrade} is degraded for the last {args.degrade_minutes} minutes.")
        return

    ensure_local(args.base_url, allow_remote=args.allow_remote)
    async with httpx2.AsyncClient(base_url=args.base_url, timeout=10) as client:
        try:
            health = await client.get("/health")
        except httpx2.TransportError:
            raise SystemExit(f"No server at {args.base_url}; start it with `make run`.") from None
        if health.status_code != 200:
            raise SystemExit(f"Server is not ready (/health returned {health.status_code}).")
        print(
            f"Sending traffic to {args.base_url} for {args.duration} s "
            f"with {args.concurrency} workers..."
        )
        tally = await run_live(
            client, duration_seconds=args.duration, concurrency=args.concurrency, rng=rng
        )
    print(tally.summary())


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
