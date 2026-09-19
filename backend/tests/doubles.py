"""Test stand-ins for randomness and time, shared by the simulation and route tests."""

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
