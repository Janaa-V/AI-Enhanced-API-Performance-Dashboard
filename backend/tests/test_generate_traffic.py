"""The traffic generator's pure parts: mix, payloads, safety checks, synthetic rows, summary."""

import asyncio
import random
from collections import Counter
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas.demo import CreateOrderRequest
from app.services.demo_data import UnknownProductError, price_order
from app.services.simulation import DEFAULT_PROFILES
from scripts.generate_traffic import (
    ROUTES,
    BackfillRefused,
    Degraded,
    Tally,
    backfill,
    build_request,
    choose_route,
    ensure_local,
    order_body,
    p95,
    parse_args,
    run_live,
    synthetic_logs,
)

END = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)


def is_accepted(body: dict) -> bool:
    """Whether the real POST /demo/orders would accept this body."""
    try:
        price_order(CreateOrderRequest.model_validate(body).items)
    except (ValidationError, UnknownProductError):
        return False
    return True


def test_routes_are_chosen_in_proportion_to_their_weights() -> None:
    rng = random.Random(1)
    counts = Counter(choose_route(rng) for _ in range(20_000))
    total_weight = sum(route.weight for route in ROUTES)
    for route in ROUTES:
        assert counts[route] / 20_000 == pytest.approx(route.weight / total_weight, abs=0.01)


def test_valid_orders_are_accepted_and_invalid_ones_rejected_by_the_real_rules() -> None:
    rng = random.Random(2)
    assert all(is_accepted(order_body(rng, valid=True)) for _ in range(200))
    assert not any(is_accepted(order_body(rng, valid=False)) for _ in range(200))


def test_about_one_order_in_ten_is_invalid() -> None:
    rng = random.Random(3)
    post = next(route for route in ROUTES if route.method == "POST")
    bodies = [build_request(post, rng)[1] for _ in range(5_000)]
    invalid = sum(not is_accepted(body) for body in bodies if body is not None)
    assert invalid / 5_000 == pytest.approx(0.1, abs=0.02)


def test_search_requests_carry_a_query_and_reads_have_no_body() -> None:
    rng = random.Random(4)
    search = next(route for route in ROUTES if route.endpoint == "/demo/search")
    path, body = build_request(search, rng)
    assert path.startswith("/demo/search?q=") and body is None


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:8000", "http://localhost:8000", "http://[::1]:8000"]
)
def test_local_servers_are_allowed(url: str) -> None:
    ensure_local(url, allow_remote=False)


def test_a_remote_server_needs_an_explicit_flag() -> None:
    with pytest.raises(SystemExit, match="allow-remote"):
        ensure_local("https://api.example.com", allow_remote=False)
    ensure_local("https://api.example.com", allow_remote=True)


@pytest.mark.parametrize(
    "argv",
    [
        ["--duration", "0"],
        ["--duration", "3601"],
        ["--concurrency", "51"],
        ["--backfill-hours", "25"],
        ["--per-minute", "601"],
        ["--backfill-hours", "1", "--degrade-minutes", "0"],
        ["--backfill-hours", "1", "--degrade-minutes", "1441"],
        ["--backfill-hours", "1", "--degrade", "report"],
    ],
)
def test_arguments_are_bounded(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_defaults_are_a_short_gentle_local_run() -> None:
    args = parse_args([])
    assert (args.duration, args.concurrency, args.base_url) == (60, 5, "http://127.0.0.1:8000")
    assert args.backfill_hours is None
    assert (args.degrade, args.degrade_minutes) == (None, 30)


def test_degrading_is_only_for_backfill(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--degrade", "reports"])
    assert "SIMULATION_DEGRADED_ENDPOINT" in capsys.readouterr().err
    assert parse_args(["--backfill-hours", "2", "--degrade", "reports"]).degrade == "reports"


def test_a_degraded_backfill_gets_worse_only_after_the_given_time() -> None:
    reports = DEFAULT_PROFILES["reports"]  # 400-1500 ms, 8% failures
    since = END - timedelta(minutes=30)
    rows = synthetic_logs(
        start=END - timedelta(hours=1),
        end=END,
        per_minute=400,
        rng=random.Random(9),
        degraded=Degraded("reports", since=since),
    )

    def report_rows(*, after: bool) -> list[dict]:
        return [
            r
            for r in rows
            if r["endpoint"] == "/demo/reports" and (r["started_at"] >= since) == after
        ]

    def failure_share(selected: list[dict]) -> float:
        return sum(r["status_code"] >= 500 for r in selected) / len(selected)

    before, after = report_rows(after=False), report_rows(after=True)
    assert max(r["latency_ms"] for r in before) <= reports.max_latency_ms
    assert min(r["latency_ms"] for r in after) >= 3 * reports.min_latency_ms
    assert max(r["latency_ms"] for r in after) > reports.max_latency_ms
    assert failure_share(before) < 0.15 < failure_share(after)
    # Every other endpoint stays inside its normal range after the switch.
    others = [r for r in rows if r["endpoint"] != "/demo/reports" and r["started_at"] >= since]
    assert max(r["latency_ms"] for r in others) <= max(
        p.max_latency_ms for name, p in DEFAULT_PROFILES.items() if name != "reports"
    )


def test_synthetic_rows_follow_the_profiles_inside_the_range() -> None:
    start = END - timedelta(hours=2)
    rows = synthetic_logs(start=start, end=END, per_minute=30, rng=random.Random(5))
    assert len(rows) == 2 * 60 * 30
    assert all(start <= row["started_at"] < END for row in rows)
    profiles = {(r.method, r.endpoint): DEFAULT_PROFILES[r.profile] for r in ROUTES}
    for row in rows:
        profile = profiles[(row["method"], row["endpoint"])]
        if row["status_code"] == 422:
            assert row["method"] == "POST" and row["latency_ms"] <= 5
        elif row["status_code"] >= 500:
            assert row["status_code"] in profile.failure_statuses
        else:
            assert row["status_code"] == (201 if row["method"] == "POST" else 200)
            assert profile.min_latency_ms <= row["latency_ms"] <= profile.max_latency_ms
    statuses = Counter(row["status_code"] for row in rows)
    assert statuses[422] > 0 and sum(n for s, n in statuses.items() if s >= 500) > 0


def test_the_same_seed_gives_the_same_rows() -> None:
    def make() -> list[dict]:
        return synthetic_logs(
            start=END - timedelta(hours=1), end=END, per_minute=5, rng=random.Random(6)
        )

    assert make() == make()


async def test_backfill_never_runs_in_production() -> None:
    settings = Settings(environment="production")
    with pytest.raises(BackfillRefused, match="production"):
        await backfill(None, settings, hours=1, per_minute=1, end=END, rng=random.Random())  # type: ignore[arg-type]


def test_the_summary_counts_statuses_and_reports_p95_per_endpoint() -> None:
    tally = Tally()
    users, orders = ROUTES[0], ROUTES[-1]
    for ms in range(1, 21):
        tally.add(users, 200, float(ms))
    tally.add(orders, 503, 300.0)
    tally.add(orders, None, 0.0)
    text = tally.summary()
    assert tally.total == 21
    assert "By status: 200: 20, 503: 1" in text
    assert "Connection failures: 1" in text
    assert "client p95    19.1 ms" in text  # 19.05, as percentile_cont would give


def test_p95_of_a_single_value_is_that_value() -> None:
    assert p95([42.0]) == 42.0


class FakeClient:
    """Answers after a short wait and records how many requests were in flight at once."""

    def __init__(self, *, fail_every: int = 0) -> None:
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls = 0
        self.fail_every = fail_every

    async def request(self, method: str, path: str, json: object = None) -> httpx2.Response:
        self.calls += 1
        if self.fail_every and self.calls % self.fail_every == 0:
            raise httpx2.ConnectError("refused")
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.005)
        self.in_flight -= 1
        return httpx2.Response(200)


async def test_workers_send_requests_concurrently() -> None:
    client = FakeClient()
    await run_live(
        client,  # type: ignore[arg-type]
        duration_seconds=0.05,
        concurrency=4,
        rng=random.Random(7),
        pause_seconds=(0, 0),
    )
    assert client.max_in_flight == 4


async def test_connection_failures_are_counted_and_do_not_stop_the_run() -> None:
    client = FakeClient(fail_every=3)
    tally = await run_live(
        client,  # type: ignore[arg-type]
        duration_seconds=0.05,
        concurrency=2,
        rng=random.Random(8),
        pause_seconds=(0, 0),
    )
    assert tally.connection_failures == client.calls // 3
    assert tally.total == client.calls - tally.connection_failures > 0
