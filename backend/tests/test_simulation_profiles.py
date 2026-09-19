"""Verify the endpoint profiles are valid, sensible, and cannot be changed at runtime."""

import pytest

from app.services.simulation import DEFAULT_PROFILES, EndpointProfile


def test_default_profiles_cover_the_five_demo_endpoints() -> None:
    assert set(DEFAULT_PROFILES) == {"users", "products", "orders", "search", "reports"}


def test_reports_are_the_slowest_and_least_reliable() -> None:
    reports = DEFAULT_PROFILES["reports"]
    others = [profile for name, profile in DEFAULT_PROFILES.items() if name != "reports"]
    assert all(reports.max_latency_ms > other.max_latency_ms for other in others)
    assert all(reports.failure_rate > other.failure_rate for other in others)


def test_default_profiles_cannot_be_modified() -> None:
    with pytest.raises(TypeError):
        DEFAULT_PROFILES["users"] = EndpointProfile(1, 2, 0, ())  # type: ignore[index]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_latency_ms": 100, "max_latency_ms": 50, "failure_rate": 0, "failure_statuses": ()},
        {"min_latency_ms": -1, "max_latency_ms": 5, "failure_rate": 0, "failure_statuses": ()},
        {"min_latency_ms": 1, "max_latency_ms": 5, "failure_rate": 1.5, "failure_statuses": (500,)},
        {"min_latency_ms": 1, "max_latency_ms": 5, "failure_rate": 0.1, "failure_statuses": ()},
        {"min_latency_ms": 1, "max_latency_ms": 5, "failure_rate": 0.1, "failure_statuses": (404,)},
    ],
    ids=["min-above-max", "negative-latency", "rate-above-one", "no-statuses", "client-error"],
)
def test_invalid_profiles_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        EndpointProfile(**kwargs)


def test_a_profile_that_never_fails_needs_no_statuses() -> None:
    EndpointProfile(1, 5, 0, ())
