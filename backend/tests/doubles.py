"""Test stand-ins for randomness and time, shared by the simulation and route tests."""

import asyncio
from collections.abc import Callable, Sequence

from fastapi.testclient import TestClient


class ScriptedRandom:
    """A random source whose answers the test chooses; no subclassing needed."""

    def __init__(self, *, latency_fraction: float = 0.5, roll: float = 0.999) -> None:
        self.latency_fraction = latency_fraction
        self.roll = roll

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.latency_fraction

    def random(self) -> float:
        return self.roll

    def choice(self, seq: Sequence[int]) -> int:
        return seq[0]


class FakeSleep:
    """Records requested delays instead of waiting."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


MakeClient = Callable[..., tuple[TestClient, FakeSleep]]


class FakeClock:
    """A clock a test moves by hand, so latency is exact and needs no real waiting."""

    START = 1000.0

    def __init__(self) -> None:
        self.now = self.START

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class InMemoryRecorder:
    """Collects records instead of saving them. Optionally blocks, slows, or fails."""

    def __init__(
        self, *, gate: "asyncio.Event | None" = None, error: Exception | None = None
    ) -> None:
        self.records: list = []
        self.events: list[str] = []
        self.gate = gate
        self.error = error

    async def record(self, record: object) -> None:
        self.events.append("record")
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        self.records.append(record)
