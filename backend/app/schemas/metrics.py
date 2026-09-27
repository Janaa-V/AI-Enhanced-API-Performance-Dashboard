"""Response models for GET /metrics.

Rules shared by every model:
- Latency is in milliseconds and rates are fractions from 0 to 1; the client rounds for display.
- Timestamps are timezone-aware UTC.
- Errors are server errors (5xx). Client errors (4xx) are counted separately and are not failures.
- With no requests, counts are 0 and averages, p95 and error rate are null, never 0.
- Nullable fields are still required, so generated client types read `number | null`.
"""

from pydantic import AwareDatetime, BaseModel, Field


class MetricsWindow(BaseModel):
    start: AwareDatetime
    end: AwareDatetime  # exclusive: rows are included when start <= started_at < end
    window_minutes: int = Field(ge=1, le=1440)
    bucket_minutes: int = Field(ge=1, le=60)


class RequestStats(BaseModel):
    """Counts and latency for a set of requests: the whole window, one endpoint or one bucket."""

    total_requests: int = Field(ge=0)
    server_errors: int = Field(ge=0)  # 5xx; the only statuses in error_rate
    client_errors: int = Field(ge=0)  # 4xx
    error_rate: float | None = Field(ge=0, le=1)  # server_errors / total_requests
    avg_latency_ms: float | None = Field(ge=0)
    p95_latency_ms: float | None = Field(ge=0)  # interpolated (percentile_cont)


class Summary(RequestStats):
    requests_per_minute: float = Field(ge=0)  # total_requests / window_minutes


class EndpointMetrics(RequestStats):
    # GET and POST /demo/orders share a path but not a behaviour, so the method is part of the key.
    method: str
    endpoint: str  # route template, for example /demo/users


class StatusCodeCount(BaseModel):
    status_code: int = Field(ge=100, le=599)
    count: int = Field(ge=1)  # only statuses that occurred are listed


class TrendBucket(RequestStats):
    start: AwareDatetime
    end: AwareDatetime  # the first and last buckets are clipped to the window


class EndpointTrend(BaseModel):
    method: str
    endpoint: str
    buckets: list[TrendBucket]


class LatencyTrend(BaseModel):
    # Every bucket in the window is present, empty ones included, so charts show gaps.
    overall: list[TrendBucket]
    by_endpoint: list[EndpointTrend]


class RecentRequest(BaseModel):
    id: int
    method: str
    endpoint: str
    status_code: int = Field(ge=100, le=599)
    latency_ms: float = Field(ge=0)
    started_at: AwareDatetime


class MetricsResponse(BaseModel):
    window: MetricsWindow
    summary: Summary
    endpoints: list[EndpointMetrics]
    status_codes: list[StatusCodeCount]  # ascending by status code
    latency_trend: LatencyTrend
    recent_requests: list[RecentRequest]  # newest first, id as tie-breaker
