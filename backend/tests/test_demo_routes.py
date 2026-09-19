"""Verify the demo routes end to end, with the simulator's dice and clock controlled."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.errors import error_detail
from app.config import Settings
from app.main import create_app
from app.services.simulation import DEFAULT_PROFILES
from tests.doubles import MakeClient

# (URL name, key holding the list in the response, how many items it has)
LIST_ROUTES = [("users", "users", 3), ("products", "products", 4), ("orders", "orders", 3)]
# Profiles that back a GET route (orders_create backs POST /demo/orders).
GET_ENDPOINTS = [name for name in DEFAULT_PROFILES if name != "orders_create"]


@pytest.mark.parametrize(("name", "key", "count"), LIST_ROUTES)
def test_list_routes_return_their_fixed_data(
    make_client: MakeClient, name: str, key: str, count: int
) -> None:
    client, _ = make_client()
    response = client.get(f"/demo/{name}")
    assert response.status_code == 200
    assert len(response.json()[key]) == count


def test_the_report_route_returns_a_summary(make_client: MakeClient) -> None:
    client, _ = make_client()
    body = client.get("/demo/reports").json()
    assert body["title"] == "Weekly summary"
    assert len(body["rows"]) == 3


@pytest.mark.parametrize("endpoint", GET_ENDPOINTS)
def test_each_route_waits_its_simulated_latency(make_client: MakeClient, endpoint: str) -> None:
    client, sleep = make_client(latency_fraction=0.5)
    client.get(f"/demo/{endpoint}")
    profile = DEFAULT_PROFILES[endpoint]
    midpoint = (profile.min_latency_ms + profile.max_latency_ms) / 2 / 1000
    assert sleep.delays == [pytest.approx(midpoint)]


@pytest.mark.parametrize("endpoint", GET_ENDPOINTS)
def test_a_forced_failure_uses_the_shared_error_body(
    make_client: MakeClient, endpoint: str
) -> None:
    client, sleep = make_client(roll=0.0)
    response = client.get(f"/demo/{endpoint}")
    status = DEFAULT_PROFILES[endpoint].failure_statuses[0]
    detail = error_detail(status)
    assert response.status_code == status
    assert response.json() == {"error": {"code": detail.code, "message": detail.message}}
    assert len(sleep.delays) == 1  # the failing request still waited first


def test_search_filters_by_the_query_ignoring_case(make_client: MakeClient) -> None:
    client, _ = make_client()
    body = client.get("/demo/search", params={"q": "LAP"}).json()
    assert body["query"] == "LAP"
    assert body["total"] == 2
    assert {item["name"] for item in body["results"]} == {"Laptop Pro", "Laptop Stand"}


def test_search_without_a_query_returns_everything(make_client: MakeClient) -> None:
    client, _ = make_client()
    assert client.get("/demo/search").json()["total"] == 4


def test_search_with_no_match_returns_an_empty_list(make_client: MakeClient) -> None:
    client, _ = make_client()
    body = client.get("/demo/search", params={"q": "zzz"}).json()
    assert (body["total"], body["results"]) == (0, [])


def test_search_accepts_the_longest_allowed_query(make_client: MakeClient) -> None:
    client, _ = make_client()
    assert client.get("/demo/search", params={"q": "x" * 100}).status_code == 200


def test_an_invalid_request_is_rejected_before_any_simulation(make_client: MakeClient) -> None:
    """Even when the dice say "fail", bad input gets a 422 immediately, not a simulated 5xx."""
    client, sleep = make_client(roll=0.0)
    response = client.get("/demo/search", params={"q": "x" * 101})
    assert response.status_code == 422
    assert sleep.delays == []


def test_the_health_route_is_never_simulated(make_client: MakeClient) -> None:
    client, sleep = make_client(roll=0.0)
    assert client.get("/health").status_code == 200
    assert sleep.delays == []


def test_the_docs_list_every_route_with_exactly_its_possible_failures(
    make_client: MakeClient,
) -> None:
    client, _ = make_client()
    paths = client.get("/openapi.json").json()["paths"]
    for endpoint in GET_ENDPOINTS:
        profile = DEFAULT_PROFILES[endpoint]
        documented = set(paths[f"/demo/{endpoint}"]["get"]["responses"])
        assert {"200"} | {str(s) for s in profile.failure_statuses} <= documented


def test_the_configured_scales_reach_the_real_simulator(monkeypatch: pytest.MonkeyPatch) -> None:
    """No overrides: with both scales at zero the real simulator never waits or fails."""
    settings = Settings(
        _env_file=None,
        db_password="unused",
        simulation_latency_scale=0,
        simulation_failure_scale=0,
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.Database", lambda settings: AsyncMock())
    with TestClient(create_app()) as client:
        simulator = client.app.state.simulator
        plans = [simulator.plan(DEFAULT_PROFILES["reports"]) for _ in range(500)]
    assert all(plan.delay_seconds == 0 and plan.failure_status is None for plan in plans)
