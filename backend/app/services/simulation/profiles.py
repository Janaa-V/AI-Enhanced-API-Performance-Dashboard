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
    }
)
