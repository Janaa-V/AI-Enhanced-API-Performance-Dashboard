"""Turns a profile into a delay and an optional failure.

The decision (`plan`) is separate from the side effects (`simulate`), and both the
random source and the sleep function are injected, so tests control every outcome
and never wait in real time.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.services.simulation.profiles import EndpointProfile

Sleep = Callable[[float], Awaitable[None]]


class RandomSource(Protocol):
    """The three random operations the simulator needs; `random.Random` satisfies it."""

    def uniform(self, a: float, b: float) -> float: ...

    def random(self) -> float: ...

    def choice(self, seq: Sequence[int]) -> int: ...


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one simulated request will do: wait, then optionally fail."""

    delay_seconds: float
    failure_status: int | None


class SimulatedFailure(Exception):
    """Raised when a simulated request is chosen to fail."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"Simulated failure with status {status_code}")
        self.status_code = status_code


class Simulator:
    def __init__(
        self,
        *,
        latency_scale: float = 1.0,
        failure_scale: float = 1.0,
        rng: RandomSource | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        if latency_scale < 0 or failure_scale < 0:
            raise ValueError("Simulation scales must not be negative.")
        self._latency_scale = latency_scale
        self._failure_scale = failure_scale
        # Simulation needs statistical variety, not cryptographic randomness.
        self._rng: RandomSource = rng if rng is not None else random.Random()  # noqa: S311
        self._sleep: Sleep = sleep if sleep is not None else asyncio.sleep

    def plan(self, profile: EndpointProfile) -> Outcome:
        """Decide one request's delay and outcome. Pure and synchronous.

        With no await between the random draws, concurrent requests sharing this
        simulator can never interleave them.
        """
        latency_ms = self._rng.uniform(profile.min_latency_ms, profile.max_latency_ms)
        # A probability above 1 (from a large scale) simply means "always fails".
        fails = self._rng.random() < profile.failure_rate * self._failure_scale
        return Outcome(
            delay_seconds=latency_ms * self._latency_scale / 1000,
            failure_status=self._rng.choice(profile.failure_statuses) if fails else None,
        )

    async def simulate(self, profile: EndpointProfile) -> None:
        """Wait the planned delay, then raise if the request should fail.

        A failing request still takes its full time first, like a real timeout would.
        """
        outcome = self.plan(profile)
        await self._sleep(outcome.delay_seconds)
        if outcome.failure_status is not None:
            raise SimulatedFailure(outcome.failure_status)
