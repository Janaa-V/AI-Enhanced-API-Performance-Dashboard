"""Request and response models for POST /analyze.

`Analysis` is also the schema the AI provider must follow, so its limits keep the answer
short and checkable:
- observations point at an endpoint from the input (or the whole API) and a fixed metric;
- hypotheses are at most "medium" confidence, because latency and status codes alone
  cannot prove a root cause;
- unknown fields are rejected, so a provider cannot smuggle in extra content.
"""

from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

# The statistics an observation can refer to; every one appears in the analysis input.
Metric = Literal[
    "total_requests",
    "requests_per_minute",
    "error_rate",
    "client_errors",
    "avg_latency_ms",
    "p95_latency_ms",
]


# Text that is not blank once trimmed, with a length limit the generated schema shows.
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Sentence = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Paragraph = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Optional so the server's METRICS_WINDOW_MINUTES applies, as for GET /metrics.
    window_minutes: int | None = Field(default=None, ge=1, le=1440)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: ShortText | None  # "GET /demo/reports"; null for the whole API
    metric: Metric
    text: Paragraph


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Paragraph
    confidence: Literal["low", "medium"]


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: Sentence
    observations: list[Observation] = Field(max_length=5)
    hypotheses: list[Hypothesis] = Field(max_length=3)
    next_steps: list[Sentence] = Field(max_length=3)


class AnalysisWindow(BaseModel):
    start: AwareDatetime
    end: AwareDatetime  # exclusive, as in /metrics
    window_minutes: int = Field(ge=1, le=1440)


class AnalysisResponse(BaseModel):
    """One shape for both outcomes, so clients handle a single type.

    With too little traffic the status is "no_data" and provider, model and analysis are
    null; no provider was called.
    """

    status: Literal["ok", "no_data"]
    window: AnalysisWindow
    generated_at: AwareDatetime
    provider: str | None
    model: str | None
    cached: bool
    analysis: Analysis | None

    @model_validator(mode="after")
    def fields_match_the_status(self) -> Self:
        produced = (self.provider, self.model, self.analysis)
        if self.status == "ok" and any(field is None for field in produced):
            raise ValueError('An "ok" response needs provider, model and analysis.')
        if self.status == "no_data" and any(field is not None for field in produced):
            raise ValueError('A "no_data" response has no provider, model or analysis.')
        return self
