"""What the AI provider is shown: aggregates of one window, never individual requests.

Each endpoint also carries its numbers for the first and second half of the window, so
the model can say whether something is getting worse, not only how it is now. Numbers
are rounded (0.1 ms, three decimals for rates) to save tokens and to give the model
values it can quote exactly; GET /metrics stays unrounded.
"""

from collections.abc import Sequence
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.metrics import EndpointMetrics, RequestStats, StatusCodeCount, Summary
from app.services.metrics import (
    TimeWindow,
    begin_snapshot,
    endpoint_metrics,
    status_codes,
    summary,
)


class InputModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InputWindow(InputModel):
    start: AwareDatetime
    end: AwareDatetime  # exclusive
    minutes: int = Field(ge=1, le=1440)


class HalfStats(InputModel):
    total_requests: int = Field(ge=0)
    error_rate: float | None
    p95_latency_ms: float | None


class SummaryInput(InputModel):
    total_requests: int = Field(ge=0)
    requests_per_minute: float
    error_rate: float | None
    client_errors: int = Field(ge=0)
    avg_latency_ms: float | None
    p95_latency_ms: float | None


class EndpointInput(InputModel):
    endpoint: str  # method and route template, for example "GET /demo/reports"
    total_requests: int = Field(ge=0)
    error_rate: float | None
    client_errors: int = Field(ge=0)
    avg_latency_ms: float | None
    p95_latency_ms: float | None
    first_half: HalfStats
    second_half: HalfStats


class AnalysisInput(InputModel):
    window: InputWindow
    summary: SummaryInput
    endpoints: list[EndpointInput]
    status_codes: list[StatusCodeCount]

    def endpoint_names(self) -> frozenset[str]:
        """The only endpoint names an answer may mention."""
        return frozenset(endpoint.endpoint for endpoint in self.endpoints)


EMPTY_HALF = HalfStats(total_requests=0, error_rate=None, p95_latency_ms=None)


def endpoint_key(method: str, endpoint: str) -> str:
    """One name per endpoint, as the dashboard shows it: GET and POST /demo/orders differ."""
    return f"{method} {endpoint}"


def ms(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def rate(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def split_in_half(window: TimeWindow) -> tuple[TimeWindow, TimeWindow]:
    """Two touching half-open windows, so every row falls in exactly one half."""
    middle = window.start + (window.end - window.start) / 2
    return TimeWindow(start=window.start, end=middle), TimeWindow(start=middle, end=window.end)


def half_stats(stats: RequestStats | None) -> HalfStats:
    if stats is None:  # no requests to this endpoint in that half
        return EMPTY_HALF
    return HalfStats(
        total_requests=stats.total_requests,
        error_rate=rate(stats.error_rate),
        p95_latency_ms=ms(stats.p95_latency_ms),
    )


def endpoint_input(
    stats: EndpointMetrics,
    first_half: dict[str, EndpointMetrics],
    second_half: dict[str, EndpointMetrics],
) -> EndpointInput:
    key = endpoint_key(stats.method, stats.endpoint)
    return EndpointInput(
        endpoint=key,
        total_requests=stats.total_requests,
        error_rate=rate(stats.error_rate),
        client_errors=stats.client_errors,
        avg_latency_ms=ms(stats.avg_latency_ms),
        p95_latency_ms=ms(stats.p95_latency_ms),
        first_half=half_stats(first_half.get(key)),
        second_half=half_stats(second_half.get(key)),
    )


def build_analysis_input(
    *,
    window: TimeWindow,
    totals: Summary,
    endpoints: Sequence[EndpointMetrics],
    first_half: Sequence[EndpointMetrics],
    second_half: Sequence[EndpointMetrics],
    codes: Sequence[StatusCodeCount],
) -> AnalysisInput:
    """Combine the query results into the model's input. Pure, so tests need no database."""
    early = {endpoint_key(e.method, e.endpoint): e for e in first_half}
    late = {endpoint_key(e.method, e.endpoint): e for e in second_half}
    return AnalysisInput(
        window=InputWindow(start=window.start, end=window.end, minutes=round(window.minutes)),
        summary=SummaryInput(
            total_requests=totals.total_requests,
            requests_per_minute=round(totals.requests_per_minute, 1),
            error_rate=rate(totals.error_rate),
            client_errors=totals.client_errors,
            avg_latency_ms=ms(totals.avg_latency_ms),
            p95_latency_ms=ms(totals.p95_latency_ms),
        ),
        endpoints=[endpoint_input(stats, early, late) for stats in endpoints],
        status_codes=list(codes),
    )


async def collect_analysis_input(
    session: AsyncSession, *, end: datetime, window_minutes: int
) -> AnalysisInput:
    """The model's input, read from one consistent snapshot like GET /metrics."""
    window = TimeWindow.ending_at(end, window_minutes)
    early, late = split_in_half(window)
    await begin_snapshot(session)
    # One session runs one query at a time, so these are awaited in turn.
    return build_analysis_input(
        window=window,
        totals=await summary(session, window),
        endpoints=await endpoint_metrics(session, window),
        first_half=await endpoint_metrics(session, early),
        second_half=await endpoint_metrics(session, late),
        codes=await status_codes(session, window),
    )
