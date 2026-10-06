"""How each simulated demo endpoint behaves. Data only: tune the numbers here."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class EndpointProfile:
    min_latency_ms: float
    max_latency_ms: float
    failure_rate: float  # probability between 0 and 1
    failure_statuses: tuple[int, ...]  # server-error codes a failure chooses from

    def __post_init__(self) -> None:
        if not 0 <= self.min_latency_ms <= self.max_latency_ms:
            raise ValueError("Latency range must satisfy 0 <= min <= max.")
        if not 0 <= self.failure_rate <= 1:
            raise ValueError("Failure rate must be between 0 and 1.")
        if any(not 500 <= status <= 599 for status in self.failure_statuses):
            raise ValueError("Simulated failures must use server-error statuses (500-599).")
        if self.failure_rate > 0 and not self.failure_statuses:
            raise ValueError("An endpoint that can fail needs at least one failure status.")


# Reports are the slowest and least reliable; simple reads are fast and rarely fail.
# Read-only, so no code can change the profiles while the application runs.
DEFAULT_PROFILES: Mapping[str, EndpointProfile] = MappingProxyType(
    {
        "users": EndpointProfile(20, 80, 0.02, (500, 503)),
        "products": EndpointProfile(30, 120, 0.01, (500,)),
        "orders": EndpointProfile(60, 250, 0.05, (500, 503)),
        "search": EndpointProfile(80, 400, 0.03, (503, 504)),
        "reports": EndpointProfile(400, 1500, 0.08, (504, 500)),
        # Writes are slower and less reliable than reads.
        "orders_create": EndpointProfile(100, 400, 0.06, (500, 503)),
    }
)


@dataclass(frozen=True, slots=True)
class Degradation:
    """How much worse an endpoint behaves when it is degraded on purpose for a demo."""

    latency_factor: float
    failure_rate: float  # probability between 0 and 1

    def __post_init__(self) -> None:
        if self.latency_factor < 1:
            raise ValueError("A degradation must not make an endpoint faster.")
        if not 0 <= self.failure_rate <= 1:
            raise ValueError("Failure rate must be between 0 and 1.")


# Slow and flaky enough to stand out on the dashboard: reports go from 0.4-1.5 s to 1.2-4.5 s.
DEMO_DEGRADATION = Degradation(latency_factor=3, failure_rate=0.25)


def degrade(
    profile: EndpointProfile, degradation: Degradation = DEMO_DEGRADATION
) -> EndpointProfile:
    """A slower, less reliable copy of the profile; the original is never changed."""
    return EndpointProfile(
        profile.min_latency_ms * degradation.latency_factor,
        profile.max_latency_ms * degradation.latency_factor,
        # Never makes an endpoint more reliable than it already is.
        max(profile.failure_rate, degradation.failure_rate),
        profile.failure_statuses,
    )
