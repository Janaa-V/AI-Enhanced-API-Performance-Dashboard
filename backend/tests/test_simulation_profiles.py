"""Verify the endpoint profiles are valid, sensible, and cannot be changed at runtime."""

import pytest

from app.services.simulation import (
    DEFAULT_PROFILES,
    DEMO_DEGRADATION,
    Degradation,
    EndpointProfile,
    degrade,
)


def test_default_profiles_cover_the_demo_endpoints() -> None:
    assert set(DEFAULT_PROFILES) == {
        "users",
        "products",
        "orders",
        "search",
        "reports",
        "orders_create",
    }


def test_writes_are_slower_and_less_reliable_than_reads() -> None:
    read, write = DEFAULT_PROFILES["orders"], DEFAULT_PROFILES["orders_create"]
    assert write.max_latency_ms > read.max_latency_ms
    assert write.failure_rate > read.failure_rate


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


# --- degradation: a demo switch that makes one endpoint visibly unhealthy -------


def test_degrading_triples_latency_and_raises_failures_to_a_quarter() -> None:
    reports = DEFAULT_PROFILES["reports"]
    assert degrade(reports) == EndpointProfile(1200, 4500, 0.25, reports.failure_statuses)


def test_degrading_returns_a_copy_and_leaves_the_default_untouched() -> None:
    reports = DEFAULT_PROFILES["reports"]
    before = EndpointProfile(
        reports.min_latency_ms,
        reports.max_latency_ms,
        reports.failure_rate,
        reports.failure_statuses,
    )
    degrade(reports)
    assert DEFAULT_PROFILES["reports"] == before


def test_degrading_never_makes_an_endpoint_more_reliable() -> None:
    already_bad = EndpointProfile(10, 20, 0.5, (500,))
    assert degrade(already_bad).failure_rate == 0.5


def test_the_demo_degradation_is_clearly_visible_for_every_endpoint() -> None:
    assert DEMO_DEGRADATION.latency_factor >= 2
    for profile in DEFAULT_PROFILES.values():
        assert degrade(profile).failure_rate >= 3 * profile.failure_rate


@pytest.mark.parametrize(
    ("latency_factor", "failure_rate"),
    [(0.5, 0.2), (2, 1.5), (2, -0.1)],
    ids=["faster", "rate-above-one", "negative-rate"],
)
def test_invalid_degradations_are_rejected(latency_factor: float, failure_rate: float) -> None:
    with pytest.raises(ValueError):
        Degradation(latency_factor, failure_rate)
