"""Verify POST /demo/orders: validation, pricing, simulation, and documentation."""

from uuid import UUID

import pytest

from app.api.errors import error_detail
from app.services.simulation import DEFAULT_PROFILES
from tests.doubles import MakeClient

PROFILE = DEFAULT_PROFILES["orders_create"]  # 100-400 ms, 6% failures: 500 or 503
VALID = {
    "user_id": 2,
    "items": [{"product_id": 2, "quantity": 2}, {"product_id": 3, "quantity": 1}],
}


def test_a_valid_order_is_created_and_priced(make_client: MakeClient) -> None:
    client, _ = make_client()
    response = client.post("/demo/orders", json=VALID)
    body = response.json()
    assert response.status_code == 201
    assert (body["user_id"], body["status"], body["total"]) == (2, "created", 108.0)
    assert body["items"] == VALID["items"]
    assert UUID(body["id"]).version == 4


def test_each_order_gets_a_different_id(make_client: MakeClient) -> None:
    client, _ = make_client()
    ids = {client.post("/demo/orders", json=VALID).json()["id"] for _ in range(3)}
    assert len(ids) == 3


def test_the_write_profile_is_used_not_the_read_profile(make_client: MakeClient) -> None:
    client, sleep = make_client(latency_fraction=0.5)
    client.post("/demo/orders", json=VALID)
    midpoint = (PROFILE.min_latency_ms + PROFILE.max_latency_ms) / 2 / 1000
    assert sleep.delays == [pytest.approx(midpoint)]


INVALID_BODIES = {
    "no-items": {"user_id": 1, "items": []},
    "too-many-items": {"user_id": 1, "items": [{"product_id": 1, "quantity": 1}] * 21},
    "zero-quantity": {"user_id": 1, "items": [{"product_id": 1, "quantity": 0}]},
    "huge-quantity": {"user_id": 1, "items": [{"product_id": 1, "quantity": 100}]},
    "zero-product-id": {"user_id": 1, "items": [{"product_id": 0, "quantity": 1}]},
    "zero-user-id": {"user_id": 0, "items": [{"product_id": 1, "quantity": 1}]},
    "missing-user-id": {"items": [{"product_id": 1, "quantity": 1}]},
    "unknown-top-level-field": {**VALID, "coupon": "FREE"},
    "unknown-item-field": {"user_id": 1, "items": [{"product_id": 1, "quantity": 1, "qty": 5}]},
    "text-quantity": {"user_id": 1, "items": [{"product_id": 1, "quantity": "two"}]},
    "items-not-a-list": {"user_id": 1, "items": "everything"},
}


@pytest.mark.parametrize("body", INVALID_BODIES.values(), ids=INVALID_BODIES.keys())
def test_invalid_bodies_are_rejected_with_422(make_client: MakeClient, body: dict) -> None:
    client, _ = make_client()
    assert client.post("/demo/orders", json=body).status_code == 422


def test_a_missing_body_is_rejected(make_client: MakeClient) -> None:
    client, _ = make_client()
    assert client.post("/demo/orders").status_code == 422


def test_an_unknown_product_is_a_422_pointing_at_the_exact_field(make_client: MakeClient) -> None:
    client, _ = make_client()
    body = {
        "user_id": 1,
        "items": [{"product_id": 2, "quantity": 1}, {"product_id": 99, "quantity": 1}],
    }
    response = client.post("/demo/orders", json=body)
    error = response.json()["detail"][0]
    assert response.status_code == 422
    assert error["loc"] == ["body", "items", 1, "product_id"]
    assert "99" in error["msg"]


@pytest.mark.parametrize(
    "body",
    [INVALID_BODIES["zero-quantity"], {"user_id": 1, "items": [{"product_id": 99, "quantity": 1}]}],
    ids=["invalid-shape", "unknown-product"],
)
def test_bad_orders_are_rejected_before_any_simulation(make_client: MakeClient, body: dict) -> None:
    """Even when the dice say "fail", bad input gets a 422 immediately, not a simulated 5xx."""
    client, sleep = make_client(roll=0.0)
    assert client.post("/demo/orders", json=body).status_code == 422
    assert sleep.delays == []


def test_a_valid_order_can_fail_with_the_shared_error_body(make_client: MakeClient) -> None:
    client, sleep = make_client(roll=0.0)
    response = client.post("/demo/orders", json=VALID)
    detail = error_detail(PROFILE.failure_statuses[0])
    assert response.status_code == PROFILE.failure_statuses[0]
    assert response.json() == {"error": {"code": detail.code, "message": detail.message}}
    assert len(sleep.delays) == 1


def test_listing_orders_still_works_on_the_same_path(make_client: MakeClient) -> None:
    client, _ = make_client()
    assert client.get("/demo/orders").status_code == 200


def test_the_docs_describe_the_post_and_its_failures(make_client: MakeClient) -> None:
    client, _ = make_client()
    path = client.get("/openapi.json").json()["paths"]["/demo/orders"]
    assert {"get", "post"} <= set(path)
    documented = set(path["post"]["responses"])
    assert {"201", "422"} | {str(s) for s in PROFILE.failure_statuses} <= documented


def test_browsers_may_call_it_from_the_dev_frontend(make_client: MakeClient) -> None:
    client, _ = make_client()
    response = client.options(
        "/demo/orders",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
