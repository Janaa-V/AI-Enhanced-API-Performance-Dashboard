"""Verify the middleware inside a real FastAPI app with the real demo routes."""

import time
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.api.errors import register_error_handlers
from app.api.routers.demo import router as demo_router
from app.middleware.request_logging import RequestLoggingMiddleware
from app.services.simulation import Simulator
from tests.doubles import FakeSleep, InMemoryRecorder, ScriptedRandom

ORIGIN = "http://localhost:5173"


def build_app(recorder: InMemoryRecorder, *, roll: float = 0.999) -> FastAPI:
    application = FastAPI()
    application.state.simulator = Simulator(rng=ScriptedRandom(roll=roll), sleep=FakeSleep())
    register_error_handlers(application)
    application.include_router(demo_router)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/demo/items/{item_id}")
    async def item(item_id: int) -> dict[str, int]:
        return {"id": item_id}

    @application.get("/demo/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    # Added first, so it is the innermost layer (CORS wraps it), as in the real app.
    application.add_middleware(RequestLoggingMiddleware, get_recorder=lambda scope: recorder)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[ORIGIN],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    return application


@pytest.fixture
def setup() -> Iterator[tuple[TestClient, InMemoryRecorder]]:
    recorder = InMemoryRecorder()
    with TestClient(build_app(recorder), raise_server_exceptions=False) as client:
        yield client, recorder


def wait_for(recorder: InMemoryRecorder, count: int) -> None:
    """Crash records are saved in a background task; give it a moment."""
    deadline = time.monotonic() + 2
    while len(recorder.records) < count and time.monotonic() < deadline:
        time.sleep(0.01)


@pytest.mark.parametrize("name", ["users", "products", "orders", "reports"])
def test_each_get_route_is_recorded_once_under_its_template(setup, name: str) -> None:
    client, recorder = setup
    assert client.get(f"/demo/{name}").status_code == 200
    (record,) = recorder.records
    assert (record.method, record.endpoint, record.status_code) == ("GET", f"/demo/{name}", 200)
    assert record.latency_ms >= 0
    assert record.started_at.tzinfo is not None


def test_a_post_is_recorded_with_its_method_and_201(setup) -> None:
    client, recorder = setup
    body = {"user_id": 1, "items": [{"product_id": 1, "quantity": 1}]}
    assert client.post("/demo/orders", json=body).status_code == 201
    (record,) = recorder.records
    assert (record.method, record.endpoint, record.status_code) == ("POST", "/demo/orders", 201)


def test_a_query_string_is_never_recorded(setup) -> None:
    client, recorder = setup
    client.get("/demo/search", params={"q": "laptop"})
    assert recorder.records[0].endpoint == "/demo/search"


def test_a_validation_error_is_recorded_as_422_under_the_template(setup) -> None:
    client, recorder = setup
    assert client.get("/demo/search", params={"q": "x" * 101}).status_code == 422
    (record,) = recorder.records
    assert (record.endpoint, record.status_code) == ("/demo/search", 422)


def test_a_path_parameter_is_recorded_as_a_template(setup) -> None:
    client, recorder = setup
    client.get("/demo/items/7")
    client.get("/demo/items/8")
    assert [r.endpoint for r in recorder.records] == ["/demo/items/{item_id}"] * 2


def test_a_wrong_method_is_recorded_as_405(setup) -> None:
    client, recorder = setup
    assert client.delete("/demo/users").status_code == 405
    assert (recorder.records[0].endpoint, recorder.records[0].status_code) == ("/demo/users", 405)


def test_a_simulated_failure_is_recorded_with_its_error_status() -> None:
    recorder = InMemoryRecorder()
    with TestClient(build_app(recorder, roll=0.0)) as client:
        assert client.get("/demo/reports").status_code == 504
        assert client.get("/demo/users").status_code == 500
    assert [(r.endpoint, r.status_code) for r in recorder.records] == [
        ("/demo/reports", 504),
        ("/demo/users", 500),
    ]


@pytest.mark.parametrize("path", ["/health", "/docs", "/openapi.json"])
def test_monitoring_and_docs_routes_are_never_recorded(setup, path: str) -> None:
    client, recorder = setup
    client.get(path)
    assert recorder.records == []


def test_unknown_demo_paths_are_not_recorded_but_still_return_404(setup) -> None:
    client, recorder = setup
    assert client.get("/demo/nothing").status_code == 404
    assert recorder.records == []


def test_a_browser_preflight_is_not_recorded(setup) -> None:
    client, recorder = setup
    response = client.options(
        "/demo/orders",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert recorder.records == []


def test_a_crashing_route_returns_500_and_is_recorded_as_500(setup) -> None:
    client, recorder = setup
    assert client.get("/demo/boom").status_code == 500
    wait_for(recorder, 1)
    (record,) = recorder.records
    assert (record.endpoint, record.status_code) == ("/demo/boom", 500)


def test_every_request_creates_exactly_one_record(setup) -> None:
    client, recorder = setup
    for _ in range(5):
        client.get("/demo/users")
    client.get("/health")
    client.get("/demo/nothing")
    assert len(recorder.records) == 5
