"""One real call to the configured AI provider. Opt-in: make test-live, never in CI.

It proves what mocks cannot: that the real API still accepts our request and schema and
returns an answer that meets the contract. It costs one request of the free quota.
"""

import json
from datetime import UTC, datetime

import httpx2
import pytest

from app.config import Settings
from app.schemas.metrics import EndpointMetrics, StatusCodeCount, Summary
from app.services.analysis.input import build_analysis_input
from app.services.analysis.providers import build_provider
from app.services.metrics import TimeWindow

pytestmark = pytest.mark.live


def sample_input() -> str:
    """A small, realistic input: reports got slower and less reliable in the second half."""

    def stats(total: int, errors: int, p95: float) -> dict:
        return {
            "total_requests": total,
            "server_errors": errors,
            "client_errors": 0,
            "error_rate": errors / total,
            "avg_latency_ms": p95 / 2,
            "p95_latency_ms": p95,
        }

    def reports(total: int, errors: int, p95: float) -> EndpointMetrics:
        return EndpointMetrics.model_validate(
            stats(total, errors, p95) | {"method": "GET", "endpoint": "/demo/reports"}
        )

    built = build_analysis_input(
        window=TimeWindow.ending_at(datetime(2026, 10, 5, 17, 0, tzinfo=UTC), 60),
        totals=Summary.model_validate(stats(120, 20, 4120.5) | {"requests_per_minute": 2.0}),
        endpoints=[reports(120, 20, 4120.5)],
        first_half=[reports(60, 5, 1420.0)],
        second_half=[reports(60, 15, 4310.7)],
        codes=[
            StatusCodeCount(status_code=200, count=100),
            StatusCodeCount(status_code=504, count=20),
        ],
    )
    return json.dumps(built.model_dump(mode="json"))


async def test_the_configured_provider_returns_a_valid_analysis() -> None:
    settings = Settings()
    if settings.ai_provider not in ("groq", "gemini"):
        pytest.skip("Set AI_PROVIDER to groq or gemini and AI_API_KEY in .env to run this.")
    async with httpx2.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
        provider = build_provider(settings, client)
        assert provider is not None
        answer = await provider.complete(
            system=(
                "You review API performance metrics. Use only the numbers given. Reply in the "
                "required JSON format."
            ),
            user=sample_input(),
        )
    # The contract was already enforced while parsing; check it is about this data.
    assert answer.headline
    assert all(o.endpoint in (None, "GET /demo/reports") for o in answer.observations)
