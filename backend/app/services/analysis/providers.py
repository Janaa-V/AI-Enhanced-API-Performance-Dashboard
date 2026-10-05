"""AI providers behind one small interface, called over plain HTTPS (no vendor SDKs).

Each adapter sends the system and user messages with the `Analysis` JSON schema, and
returns a validated `Analysis` or raises `ProviderError`. Rules shared by every adapter:
- The key travels in a header, never in the URL, because URLs end up in logs.
- Errors carry only a kind and the HTTP status, never a response body or headers, which
  could echo the request (and so the key) back.
- No retries: free-tier quota is scarce and the caller already limits concurrent calls.
"""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx2
from pydantic import SecretStr, ValidationError

from app.config import Settings
from app.schemas.analysis import Analysis, Observation

ErrorKind = Literal["timeout", "unavailable", "rate_limited", "auth", "bad_request", "bad_output"]

# The schema both providers must follow: every field required, no extra fields.
ANALYSIS_SCHEMA: Mapping[str, Any] = Analysis.model_json_schema()
TEMPERATURE = 0.2  # low: the same data should give much the same answer
MAX_OUTPUT_TOKENS = 1500  # an answer is about 400 tokens; the rest leaves room for reasoning
DEFAULT_MODELS: Mapping[str, str] = {
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-3.5-flash-lite",
}


class ProviderError(Exception):
    """A provider call failed. Safe to log: it holds no response content."""

    def __init__(
        self, kind: ErrorKind, *, status: int | None = None, retry_after: float | None = None
    ) -> None:
        detail = f" (HTTP {status})" if status is not None else ""
        super().__init__(f"AI provider error: {kind}{detail}")
        self.kind: ErrorKind = kind
        self.status = status
        self.retry_after = retry_after  # seconds, when a rate-limited provider says


class AnalysisProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    async def complete(self, *, system: str, user: str) -> Analysis: ...


def retry_after_seconds(value: str | None) -> float | None:
    """The Retry-After header in seconds; the HTTP-date form is rare here and ignored."""
    try:
        seconds = float(value) if value is not None else None
    except ValueError:
        return None
    return seconds if seconds is not None and math.isfinite(seconds) and seconds >= 0 else None


async def post_json(
    client: httpx2.AsyncClient, url: str, *, headers: Mapping[str, str], body: Mapping[str, Any]
) -> Any:
    """POST and return the decoded JSON, or raise a ProviderError that hides the details."""
    try:
        response = await client.post(url, headers=dict(headers), json=body)
    except httpx2.TimeoutException:
        raise ProviderError("timeout") from None
    except httpx2.TransportError:
        raise ProviderError("unavailable") from None
    status = response.status_code
    if status == 429:
        retry_after = retry_after_seconds(response.headers.get("retry-after"))
        raise ProviderError("rate_limited", status=status, retry_after=retry_after)
    if status in (401, 403):
        raise ProviderError("auth", status=status)
    if status >= 500:
        raise ProviderError("unavailable", status=status)
    if status >= 400:
        raise ProviderError("bad_request", status=status)
    try:
        return response.json()
    except ValueError:
        raise ProviderError("bad_output", status=status) from None


def parse_answer(text: Any) -> Analysis:
    """Validate the model's JSON text against the contract."""
    if not isinstance(text, str) or not text.strip():
        raise ProviderError("bad_output")
    try:
        return Analysis.model_validate_json(text)
    except ValidationError:
        raise ProviderError("bad_output") from None


@dataclass(frozen=True, slots=True)
class GroqProvider:
    """Groq's OpenAI-compatible chat API, with strict JSON-schema output."""

    client: httpx2.AsyncClient
    api_key: SecretStr = field(repr=False)
    model: str = DEFAULT_MODELS["groq"]
    name: str = "groq"
    url: str = "https://api.groq.com/openai/v1/chat/completions"

    async def complete(self, *, system: str, user: str) -> Analysis:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # Constrained decoding: the reply always has the schema's shape.
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "analysis", "strict": True, "schema": ANALYSIS_SCHEMA},
            },
            "temperature": TEMPERATURE,
            "max_completion_tokens": MAX_OUTPUT_TOKENS,
        }
        if self.model.startswith("openai/gpt-oss"):
            # Reasoning tokens count towards the limit; a summary of numbers needs little.
            body["reasoning_effort"] = "low"
        data = await post_json(
            self.client,
            self.url,
            headers={"Authorization": f"Bearer {self.api_key.get_secret_value()}"},
            body=body,
        )
        try:
            choice = data["choices"][0]
            finished, text = choice["finish_reason"], choice["message"].get("content")
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ProviderError("bad_output") from None
        if finished != "stop":  # "length" means the answer was cut off
            raise ProviderError("bad_output")
        return parse_answer(text)


@dataclass(frozen=True, slots=True)
class GeminiProvider:
    """Gemini's generateContent API, with a JSON schema for the response."""

    client: httpx2.AsyncClient
    api_key: SecretStr = field(repr=False)
    model: str = DEFAULT_MODELS["gemini"]
    name: str = "gemini"
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"

    async def complete(self, *, system: str, user: str) -> Analysis:
        data = await post_json(
            self.client,
            f"{self.base_url}/{self.model}:generateContent",
            headers={"x-goog-api-key": self.api_key.get_secret_value()},
            body={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": ANALYSIS_SCHEMA,
                    "temperature": TEMPERATURE,
                    "maxOutputTokens": MAX_OUTPUT_TOKENS,
                },
            },
        )
        try:
            candidate = data["candidates"][0]
            finished = candidate["finishReason"]
            text = "".join(part.get("text", "") for part in candidate["content"]["parts"])
        except (KeyError, IndexError, TypeError, AttributeError):
            # Also a blocked prompt, which comes back with no candidates.
            raise ProviderError("bad_output") from None
        if finished != "STOP":  # MAX_TOKENS, SAFETY and the rest mean no usable answer
            raise ProviderError("bad_output")
        return parse_answer(text)


def fake_answer(user: str) -> Analysis:
    """A fixed answer that names the slowest endpoint in the input, so it passes the checks."""
    try:
        endpoints = json.loads(user)["endpoints"]
        slowest = max(
            (e for e in endpoints if e["p95_latency_ms"] is not None),
            key=lambda e: e["p95_latency_ms"],
        )
        name, p95 = slowest["endpoint"], slowest["p95_latency_ms"]
    except (ValueError, KeyError, TypeError):
        return Analysis(
            headline="Fake analysis: no endpoint data to summarise.",
            observations=[],
            hypotheses=[],
            next_steps=[],
        )
    return Analysis(
        headline=f"Fake analysis: {name} is the slowest endpoint.",
        observations=[
            Observation(
                endpoint=name,
                metric="p95_latency_ms",
                text=f"{name} has the highest p95 latency, {p95} ms.",
            )
        ],
        hypotheses=[],
        next_steps=["Set AI_PROVIDER to groq or gemini for a real analysis."],
    )


@dataclass(slots=True)
class FakeProvider:
    """No network and no key: for tests and local demos (refused in production by Settings).

    Tests can make it fail with `error`, and read back the messages it received.
    """

    error: ProviderError | None = None
    name: str = "fake"
    model: str = "fake"
    calls: list[tuple[str, str]] = field(default_factory=list)

    async def complete(self, *, system: str, user: str) -> Analysis:
        self.calls.append((system, user))
        if self.error is not None:
            raise self.error
        return fake_answer(user)


def build_provider(settings: Settings, client: httpx2.AsyncClient) -> AnalysisProvider | None:
    """The configured provider, or None when AI is disabled."""
    match settings.ai_provider:
        case "disabled":
            return None
        case "fake":
            return FakeProvider()
        case "groq":
            model = settings.ai_model or DEFAULT_MODELS["groq"]
            return GroqProvider(client, settings.ai_api_key, model)
        case "gemini":
            model = settings.ai_model or DEFAULT_MODELS["gemini"]
            return GeminiProvider(client, settings.ai_api_key, model)
