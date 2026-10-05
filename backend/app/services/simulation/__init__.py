"""Simulated behaviour for the demo endpoints."""

from app.services.simulation.profiles import (
    DEFAULT_PROFILES,
    DEMO_DEGRADATION,
    Degradation,
    EndpointProfile,
    degrade,
)
from app.services.simulation.simulator import (
    Outcome,
    RandomSource,
    SimulatedFailure,
    Simulator,
    Sleep,
)

__all__ = [
    "DEFAULT_PROFILES",
    "DEMO_DEGRADATION",
    "Degradation",
    "EndpointProfile",
    "Outcome",
    "RandomSource",
    "SimulatedFailure",
    "Simulator",
    "Sleep",
    "degrade",
]
