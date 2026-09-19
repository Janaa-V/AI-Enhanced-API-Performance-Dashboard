"""Verify simulated latency and failures without real waiting or real randomness."""

import random
from collections import Counter

import pytest

from app.services.simulation import (
    DEFAULT_PROFILES,
    EndpointProfile,
    SimulatedFailure,
    Simulator,
)
from tests.doubles import FakeSleep, ScriptedRandom

USERS = DEFAULT_PROFILES["users"]  # 20-80 ms, 2% failures: 500 or 503
REPORTS = DEFAULT_PROFILES["reports"]  # 400-1500 ms, 8% failures: 504 or 500


# --- plan: the pure decision -------------------------------------------------


def test_delay_is_the_sampled_latency_in_seconds() -> None:
    outcome = Simulator(rng=ScriptedRandom(latency_fraction=0.5)).plan(USERS)
    assert outcome.delay_seconds == pytest.approx(0.05)  # halfway through 20-80 ms


def test_request_fails_when_the_roll_is_below_the_failure_rate() -> None:
    outcome = Simulator(rng=ScriptedRandom(roll=0.019)).plan(USERS)
    assert outcome.failure_status == 500  # the scripted source picks the first status


def test_request_succeeds_when_the_roll_equals_the_failure_rate() -> None:
    assert Simulator(rng=ScriptedRandom(roll=0.02)).plan(USERS).failure_status is None


def test_latency_scale_multiplies_the_delay_and_zero_removes_it() -> None:
    doubled = Simulator(rng=ScriptedRandom(), latency_scale=2).plan(USERS)
    instant = Simulator(rng=ScriptedRandom(), latency_scale=0).plan(USERS)
    assert doubled.delay_seconds == pytest.approx(0.1)
    assert instant.delay_seconds == 0


def test_failure_scale_zero_never_fails() -> None:
    simulator = Simulator(rng=ScriptedRandom(roll=0.0), failure_scale=0)
    assert all(simulator.plan(p).failure_status is None for p in DEFAULT_PROFILES.values())


def test_a_large_failure_scale_makes_every_request_fail() -> None:
    outcome = Simulator(rng=ScriptedRandom(roll=0.9999), failure_scale=100).plan(REPORTS)
    assert outcome.failure_status is not None  # 0.08 * 100 is above 1, which means "always"


def test_a_profile_with_no_failure_rate_never_fails_even_when_scaled_up() -> None:
    profile = EndpointProfile(1, 2, 0, ())
    outcome = Simulator(rng=ScriptedRandom(roll=0.0), failure_scale=100).plan(profile)
    assert outcome.failure_status is None


def test_latency_stays_inside_each_endpoints_range() -> None:
    simulator = Simulator(rng=random.Random(1234))
    for name, profile in DEFAULT_PROFILES.items():
        delays = [simulator.plan(profile).delay_seconds for _ in range(300)]
        low, high = profile.min_latency_ms / 1000, profile.max_latency_ms / 1000
        assert all(low <= delay <= high for delay in delays), name


def test_observed_failure_rate_matches_the_profile() -> None:
    simulator = Simulator(rng=random.Random(42))
    runs = 5000
    failures = sum(simulator.plan(REPORTS).failure_status is not None for _ in range(runs))
    assert 0.06 <= failures / runs <= 0.10  # reports fail 8% of the time


def test_failure_statuses_come_only_from_the_profile_and_all_appear() -> None:
    simulator = Simulator(rng=random.Random(7), failure_scale=100)
    statuses = Counter(simulator.plan(REPORTS).failure_status for _ in range(400))
    assert set(statuses) == set(REPORTS.failure_statuses)


def test_the_same_seed_reproduces_the_same_outcomes() -> None:
    first, second = Simulator(rng=random.Random(99)), Simulator(rng=random.Random(99))
    assert [first.plan(REPORTS) for _ in range(50)] == [second.plan(REPORTS) for _ in range(50)]


def test_plan_accepts_any_profile_not_just_the_defaults() -> None:
    custom = EndpointProfile(10, 10, 1, (502,))
    outcome = Simulator(rng=ScriptedRandom(roll=0.5)).plan(custom)
    assert outcome.delay_seconds == pytest.approx(0.01)
    assert outcome.failure_status == 502


def test_negative_scales_are_rejected() -> None:
    with pytest.raises(ValueError):
        Simulator(latency_scale=-1)
    with pytest.raises(ValueError):
        Simulator(failure_scale=-0.5)


# --- simulate: the side effects ----------------------------------------------


async def test_simulate_waits_the_planned_delay_and_succeeds() -> None:
    sleep = FakeSleep()
    await Simulator(rng=ScriptedRandom(latency_fraction=1.0), sleep=sleep).simulate(USERS)
    assert sleep.delays == [pytest.approx(0.08)]


async def test_a_failing_request_waits_first_then_raises_its_status() -> None:
    sleep = FakeSleep()
    simulator = Simulator(rng=ScriptedRandom(roll=0.0), sleep=sleep)
    with pytest.raises(SimulatedFailure) as failure:
        await simulator.simulate(REPORTS)
    assert failure.value.status_code == 504
    assert len(sleep.delays) == 1  # it did wait before failing


async def test_the_default_sleep_is_asyncio_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = FakeSleep()
    monkeypatch.setattr("app.services.simulation.simulator.asyncio.sleep", sleep)
    await Simulator(rng=ScriptedRandom(latency_fraction=0.5)).simulate(USERS)
    assert sleep.delays == [pytest.approx(0.05)]
