"""Verify the logging middleware by driving it directly with hand-built ASGI messages."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from starlette.requests import ClientDisconnect

from app.middleware.request_logging import RequestLoggingMiddleware
from tests.doubles import FakeClock, InMemoryRecorder

STARTED = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
ROUTE = SimpleNamespace(path="/demo/orders")


def make_scope(path: str = "/demo/orders", method: str = "POST", type_: str = "http") -> dict:
    return {"type": type_, "method": method, "path": path}


def make(app, recorder, clock: FakeClock | None = None):
    clock = clock or FakeClock()
    # The wall clock moves with the fake clock, so reading the start time late would show.
    middleware = RequestLoggingMiddleware(
        app,
        lambda scope: recorder,
        clock=clock,
        now=lambda: STARTED + timedelta(seconds=clock.now - FakeClock.START),
    )
    return middleware, clock


async def drive(middleware, scope: dict | None = None) -> list[dict]:
    """Run one request through the middleware and return what the client was sent."""
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request"}

    async def send(message: dict) -> None:
        sent.append(message)

    await middleware(scope if scope is not None else make_scope(), receive, send)
    return sent


def respond(status: int = 201, *, route=ROUTE, spend: float = 0.0, clock: FakeClock | None = None):
    """A downstream app that takes `spend` seconds, then sends a complete response."""

    async def app(scope, receive, send) -> None:
        if route is not None:
            scope["route"] = route  # what the router sets once it has matched a route
        if clock:
            clock.advance(spend)
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    return app


async def settle() -> None:
    """Let background tasks run."""
    for _ in range(10):
        await asyncio.sleep(0)


# --- what gets recorded ------------------------------------------------------


async def test_a_completed_request_is_recorded_with_every_field() -> None:
    recorder, clock = InMemoryRecorder(), FakeClock()
    middleware, _ = make(respond(201, spend=0.25, clock=clock), recorder, clock)
    await drive(middleware)
    (record,) = recorder.records
    assert (record.method, record.endpoint, record.status_code) == ("POST", "/demo/orders", 201)
    assert record.latency_ms == pytest.approx(250)
    assert record.started_at == STARTED


async def test_the_client_receives_exactly_what_the_app_sent() -> None:
    middleware, _ = make(respond(201), InMemoryRecorder())
    sent = await drive(middleware)
    assert [m["type"] for m in sent] == ["http.response.start", "http.response.body"]
    assert sent[0]["status"] == 201


async def test_error_statuses_are_recorded_as_they_were_sent() -> None:
    recorder = InMemoryRecorder()
    middleware, _ = make(respond(503), recorder)
    await drive(middleware)
    assert recorder.records[0].status_code == 503


async def test_the_route_template_is_recorded_not_the_raw_path() -> None:
    recorder = InMemoryRecorder()
    route = SimpleNamespace(path="/demo/items/{item_id}")
    middleware, _ = make(respond(200, route=route), recorder)
    await drive(middleware, make_scope("/demo/items/7", "GET"))
    assert recorder.records[0].endpoint == "/demo/items/{item_id}"


# --- latency and ordering ----------------------------------------------------


async def test_latency_stops_at_the_final_chunk_not_at_the_first_or_at_the_save() -> None:
    clock, recorder = FakeClock(), InMemoryRecorder()

    async def streaming_app(scope, receive, send) -> None:
        scope["route"] = ROUTE
        await send({"type": "http.response.start", "status": 200, "headers": []})
        clock.advance(0.1)
        await send({"type": "http.response.body", "body": b"a", "more_body": True})
        clock.advance(0.2)
        await send({"type": "http.response.body", "body": b"b", "more_body": False})

    original_record = recorder.record

    async def slow_record(record: object) -> None:
        clock.advance(5)  # the save is slow, but must not count as request time
        await original_record(record)

    recorder.record = slow_record  # type: ignore[method-assign]
    middleware, _ = make(streaming_app, recorder, clock)
    await drive(middleware)
    assert recorder.records[0].latency_ms == pytest.approx(300)


async def test_the_row_is_saved_after_the_response_has_been_sent() -> None:
    recorder = InMemoryRecorder()
    order: list[str] = []
    original_record = recorder.record

    async def tracking_record(record: object) -> None:
        order.append("saved")
        await original_record(record)

    recorder.record = tracking_record  # type: ignore[method-assign]
    inner = respond(200)

    async def app(scope, receive, send) -> None:
        async def tracking_send(message: dict) -> None:
            order.append(message["type"])
            await send(message)

        await inner(scope, receive, tracking_send)

    middleware, _ = make(app, recorder)
    await drive(middleware)
    assert order == ["http.response.start", "http.response.body", "saved"]


# --- what is not recorded ----------------------------------------------------


@pytest.mark.parametrize("path", ["/health", "/docs", "/openapi.json", "/demo", "/metrics"])
async def test_paths_outside_the_monitored_prefix_are_ignored(path: str) -> None:
    recorder = InMemoryRecorder()
    middleware, _ = make(respond(200), recorder)
    sent = await drive(middleware, make_scope(path, "GET"))
    assert recorder.records == []
    assert sent[0]["status"] == 200  # and the request still worked


@pytest.mark.parametrize("scope_type", ["websocket", "lifespan"])
async def test_non_http_traffic_passes_straight_through(scope_type: str) -> None:
    calls: list[str] = []

    async def app(scope, receive, send) -> None:
        calls.append(scope["type"])

    recorder = InMemoryRecorder()
    middleware, _ = make(app, recorder)
    scope = {"type": scope_type, "path": "/demo/orders"}
    await middleware(scope, None, None)  # type: ignore[arg-type]
    assert calls == [scope_type]
    assert recorder.records == []


async def test_requests_that_matched_no_route_are_not_recorded() -> None:
    recorder = InMemoryRecorder()
    middleware, _ = make(respond(404, route=None), recorder)
    sent = await drive(middleware, make_scope("/demo/nothing", "GET"))
    assert recorder.records == []
    assert sent[0]["status"] == 404  # the 404 itself is untouched


async def test_a_route_without_a_path_is_not_recorded() -> None:
    recorder = InMemoryRecorder()
    middleware, _ = make(respond(200, route=SimpleNamespace()), recorder)
    await drive(middleware)
    assert recorder.records == []


async def test_nothing_is_recorded_when_no_recorder_is_available() -> None:
    middleware = RequestLoggingMiddleware(respond(200), lambda scope: None)
    sent = await drive(middleware)
    assert sent[0]["status"] == 200


async def test_the_recorder_provider_receives_the_request_scope() -> None:
    seen: list[dict] = []

    def provider(scope: dict) -> None:
        seen.append(scope)

    middleware = RequestLoggingMiddleware(respond(200), provider)
    await drive(middleware)
    assert seen[0]["path"] == "/demo/orders"


# --- crashes, disconnects, cancellation ---------------------------------------


def crashing(*, after_start: bool = False):
    async def app(scope, receive, send) -> None:
        scope["route"] = ROUTE
        if after_start:
            await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("boom")

    return app


@pytest.mark.parametrize("after_start", [False, True], ids=["before-response", "mid-response"])
async def test_a_crash_is_recorded_as_500_and_raised_again_unchanged(after_start: bool) -> None:
    recorder = InMemoryRecorder()
    middleware, _ = make(crashing(after_start=after_start), recorder)
    with pytest.raises(RuntimeError, match="boom"):
        await drive(middleware)
    await settle()
    (record,) = recorder.records
    assert (record.status_code, record.endpoint) == (500, "/demo/orders")


async def test_a_crash_is_not_delayed_by_a_slow_recorder() -> None:
    """The 500 is sent only after the error passes through, so waiting here would delay it."""
    gate = asyncio.Event()
    recorder = InMemoryRecorder(gate=gate)
    middleware, _ = make(crashing(), recorder)
    with pytest.raises(RuntimeError):
        await asyncio.wait_for(drive(middleware), 1)  # would time out if it waited for the save
    assert recorder.records == []  # still blocked
    gate.set()
    await settle()
    assert recorder.records[0].status_code == 500


async def test_a_client_disconnect_is_not_recorded() -> None:
    async def app(scope, receive, send) -> None:
        scope["route"] = ROUTE
        raise ClientDisconnect

    recorder = InMemoryRecorder()
    middleware, _ = make(app, recorder)
    with pytest.raises(ClientDisconnect):
        await drive(middleware)
    await settle()
    assert recorder.records == []


async def test_a_cancelled_request_is_not_recorded_and_the_cancellation_propagates() -> None:
    async def app(scope, receive, send) -> None:
        scope["route"] = ROUTE
        await asyncio.Event().wait()

    recorder = InMemoryRecorder()
    middleware, _ = make(app, recorder)
    task = asyncio.create_task(drive(middleware))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await settle()
    assert recorder.records == []


# --- monitoring must never break requests --------------------------------------


async def test_a_failing_recorder_does_not_break_a_successful_request(
    caplog: pytest.LogCaptureFixture,
) -> None:
    middleware, _ = make(respond(200), InMemoryRecorder(error=RuntimeError("db down")))
    with caplog.at_level(logging.WARNING):
        sent = await drive(middleware)  # must not raise
    assert sent[0]["status"] == 200
    assert "Request recorder failed: RuntimeError: db down" in caplog.text


async def test_a_failing_recorder_does_not_hide_the_original_crash() -> None:
    middleware, _ = make(crashing(), InMemoryRecorder(error=ValueError("recorder bug")))
    with pytest.raises(RuntimeError, match="boom"):  # not the recorder's ValueError
        await drive(middleware)
    await settle()


async def test_concurrent_requests_do_not_mix_up_their_records() -> None:
    """One shared middleware instance, twenty interleaved requests, each with its own outcome."""
    recorder = InMemoryRecorder()

    async def app(scope, receive, send) -> None:
        i = int(scope["path"].rsplit("r", 1)[1])
        scope["route"] = SimpleNamespace(path=f"/demo/r{i}")
        for _ in range(i % 3 + 1):
            await asyncio.sleep(0)  # yield, so the requests really interleave
        await send({"type": "http.response.start", "status": 200 + i, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    shared = RequestLoggingMiddleware(app, lambda scope: recorder)
    await asyncio.gather(*(drive(shared, make_scope(f"/demo/r{i}", "GET")) for i in range(20)))
    assert sorted((r.endpoint, r.status_code) for r in recorder.records) == sorted(
        (f"/demo/r{i}", 200 + i) for i in range(20)
    )
