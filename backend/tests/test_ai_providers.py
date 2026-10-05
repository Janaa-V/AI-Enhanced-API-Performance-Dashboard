"""AI provider adapters against mocked HTTP: requests, answers, failures and secrecy."""

import json
import logging
import traceback
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.schemas.analysis import Analysis
from app.services.analysis.providers import (
    ANALYSIS_SCHEMA,
    FakeProvider,
    GeminiProvider,
    GroqProvider,
    ProviderError,
    build_provider,
)

KEY = "sk-TEST-SECRET-123"
ANSWER = {
    "headline": "Reports got slower.",
    "observations": [
        {"endpoint": "GET /demo/reports", "metric": "p95_latency_ms", "text": "p95 rose."}
    ],
    "hypotheses": [{"text": "A slow dependency.", "confidence": "medium"}],
    "next_steps": ["Check what reports calls."],
}
Handler = Callable[[httpx2.Request], httpx2.Response]


def groq_reply(content: Any = None, finish: str = "stop") -> dict[str, Any]:
    text = json.dumps(ANSWER) if content is None else content
    return {"choices": [{"finish_reason": finish, "message": {"content": text}}]}


def gemini_reply(text: str | None = None, finish: str = "STOP") -> dict[str, Any]:
    body = json.dumps(ANSWER) if text is None else text
    # Gemini may split the text across parts.
    parts = [{"text": body[:10]}, {"text": body[10:]}]
    return {"candidates": [{"finishReason": finish, "content": {"parts": parts}}]}


class Recorder:
    """A mock transport that answers with `respond` and keeps every request."""

    def __init__(self, respond: Handler) -> None:
        self.respond = respond
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self.respond(request)

    @property
    def body(self) -> dict[str, Any]:
        return json.loads(self.requests[-1].content)


def client_for(handler: Handler) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(transport=httpx2.MockTransport(handler))


def groq(handler: Handler, model: str = "openai/gpt-oss-120b") -> GroqProvider:
    return GroqProvider(client_for(handler), SecretStr(KEY), model)


def gemini(handler: Handler, model: str = "gemini-3.5-flash-lite") -> GeminiProvider:
    return GeminiProvider(client_for(handler), SecretStr(KEY), model)


def replying(status: int, body: Any = None, headers: dict[str, str] | None = None) -> Handler:
    def respond(request: httpx2.Request) -> httpx2.Response:
        if isinstance(body, str):
            return httpx2.Response(status, text=body, headers=headers)
        return httpx2.Response(status, json=body or {}, headers=headers)

    return respond


ADAPTERS = {"groq": groq, "gemini": gemini}


async def error_from(provider: GroqProvider | GeminiProvider) -> ProviderError:
    with pytest.raises(ProviderError) as caught:
        await provider.complete(system="rules", user="{}")
    return caught.value


# --- the schema both providers must follow ----------------------------------------


def objects_in(schema: Any) -> list[dict[str, Any]]:
    found = []
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            found.append(schema)
        for value in schema.values():
            found.extend(objects_in(value))
    elif isinstance(schema, list):
        for value in schema:
            found.extend(objects_in(value))
    return found


def test_the_schema_meets_strict_mode_rules() -> None:
    """Groq's strict mode needs every field required and no extra fields, on every object."""
    objects = objects_in(dict(ANALYSIS_SCHEMA))
    assert len(objects) == 3  # Analysis, Observation, Hypothesis
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])


# --- Groq --------------------------------------------------------------------------


async def test_groq_sends_the_messages_schema_and_key_and_returns_the_answer() -> None:
    recorder = Recorder(replying(200, groq_reply()))
    answer = await groq(recorder).complete(system="rules", user='{"endpoints": []}')
    assert answer == Analysis.model_validate(ANSWER)
    request = recorder.requests[0]
    assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    body = recorder.body
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["messages"] == [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": '{"endpoints": []}'},
    ]
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"] == ANALYSIS_SCHEMA
    assert (body["temperature"], body["max_completion_tokens"]) == (0.2, 1500)
    assert body["reasoning_effort"] == "low"


async def test_groq_only_asks_reasoning_models_for_low_effort() -> None:
    recorder = Recorder(replying(200, groq_reply()))
    await groq(recorder, model="llama-3.3-70b-versatile").complete(system="s", user="u")
    assert "reasoning_effort" not in recorder.body


@pytest.mark.parametrize(
    "reply",
    [
        groq_reply(finish="length"),
        groq_reply(content="not json"),
        groq_reply(content=json.dumps(ANSWER | {"headline": ""})),
        groq_reply(content=None) | {"choices": [{"finish_reason": "stop", "message": {}}]},
        {"choices": []},
        {"error": "something"},
    ],
    ids=["cut-off", "not-json", "breaks-contract", "no-content", "no-choices", "unexpected-shape"],
)
async def test_groq_answers_that_cannot_be_used_are_bad_output(reply: dict[str, Any]) -> None:
    assert (await error_from(groq(replying(200, reply)))).kind == "bad_output"


# --- Gemini ------------------------------------------------------------------------


async def test_gemini_sends_the_schema_and_key_in_a_header_and_joins_the_parts() -> None:
    recorder = Recorder(replying(200, gemini_reply()))
    answer = await gemini(recorder).complete(system="rules", user="data")
    assert answer == Analysis.model_validate(ANSWER)
    request = recorder.requests[0]
    assert str(request.url) == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.5-flash-lite:generateContent"
    )
    assert request.headers["x-goog-api-key"] == KEY
    assert KEY not in str(request.url)
    body = recorder.body
    assert body["systemInstruction"] == {"parts": [{"text": "rules"}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": "data"}]}]
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseJsonSchema"] == ANALYSIS_SCHEMA
    assert (config["temperature"], config["maxOutputTokens"]) == (0.2, 1500)


@pytest.mark.parametrize(
    "reply",
    [
        gemini_reply(finish="SAFETY"),
        gemini_reply(finish="MAX_TOKENS"),
        gemini_reply(text="not json at all"),
        {"promptFeedback": {"blockReason": "SAFETY"}},
        {"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]},
    ],
    ids=["safety", "cut-off", "not-json", "blocked-prompt", "empty"],
)
async def test_gemini_answers_that_cannot_be_used_are_bad_output(reply: dict[str, Any]) -> None:
    assert (await error_from(gemini(replying(200, reply)))).kind == "bad_output"


# --- failures shared by both adapters ----------------------------------------------


@pytest.mark.parametrize("adapter", ADAPTERS.values(), ids=ADAPTERS.keys())
@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (400, "bad_request"),
        (404, "bad_request"),
        (401, "auth"),
        (403, "auth"),
        (500, "unavailable"),
        (503, "unavailable"),
    ],
)
async def test_http_errors_become_one_error_kind(adapter: Any, status: int, kind: str) -> None:
    error = await error_from(adapter(replying(status, {"error": {"message": "nope"}})))
    assert (error.kind, error.status) == (kind, status)


@pytest.mark.parametrize("adapter", ADAPTERS.values(), ids=ADAPTERS.keys())
@pytest.mark.parametrize(
    ("header", "seconds"),
    [("12", 12.0), ("0.5", 0.5), ("soon", None), ("-3", None), ("nan", None), ("inf", None)],
)
async def test_rate_limits_keep_a_valid_retry_after(
    adapter: Any, header: str, seconds: float | None
) -> None:
    error = await error_from(adapter(replying(429, {}, headers={"retry-after": header})))
    assert (error.kind, error.retry_after) == ("rate_limited", seconds)


@pytest.mark.parametrize("adapter", ADAPTERS.values(), ids=ADAPTERS.keys())
@pytest.mark.parametrize(
    ("raised", "kind"),
    [(httpx2.ReadTimeout("slow"), "timeout"), (httpx2.ConnectError("down"), "unavailable")],
)
async def test_network_failures_become_timeout_or_unavailable(
    adapter: Any, raised: Exception, kind: str
) -> None:
    def fail(request: httpx2.Request) -> httpx2.Response:
        raise raised

    assert (await error_from(adapter(fail))).kind == kind


@pytest.mark.parametrize("adapter", ADAPTERS.values(), ids=ADAPTERS.keys())
async def test_a_reply_that_is_not_json_is_bad_output(adapter: Any) -> None:
    assert (await error_from(adapter(replying(200, "<html>oops</html>")))).kind == "bad_output"


def echoing_errors(request: httpx2.Request) -> httpx2.Response:
    """A hostile reply: rejects the call and echoes the key in its body and headers."""
    return httpx2.Response(401, json={"error": f"bad key {KEY}"}, headers={"x-echo": KEY})


def echoing_answers(request: httpx2.Request) -> httpx2.Response:
    """A hostile answer: breaks the contract with the key in the text, so validation quotes it."""
    bad = json.dumps(ANSWER | {"headline": f"{KEY} " * 30})
    if "generateContent" in str(request.url):
        return httpx2.Response(200, json=gemini_reply(text=bad))
    return httpx2.Response(200, json=groq_reply(content=bad))


@pytest.mark.parametrize("adapter", ADAPTERS.values(), ids=ADAPTERS.keys())
@pytest.mark.parametrize("hostile", [echoing_errors, echoing_answers], ids=["error", "answer"])
async def test_the_key_never_appears_in_errors_logs_or_reprs(
    adapter: Any, hostile: Handler, caplog: pytest.LogCaptureFixture
) -> None:
    provider = adapter(hostile)
    with caplog.at_level(logging.DEBUG):
        error = await error_from(provider)
        logging.getLogger("test").exception("analysis failed", exc_info=error)
    assert KEY not in "".join(traceback.format_exception(error))
    assert KEY not in caplog.text
    assert KEY not in repr(provider)


# --- the fake provider and the factory ---------------------------------------------


async def test_the_fake_names_the_slowest_endpoint_from_the_input() -> None:
    user = json.dumps(
        {
            "endpoints": [
                {"endpoint": "GET /demo/users", "p95_latency_ms": 80.0},
                {"endpoint": "GET /demo/reports", "p95_latency_ms": 4155.0},
                {"endpoint": "GET /demo/search", "p95_latency_ms": None},
            ]
        }
    )
    fake = FakeProvider()
    answer = await fake.complete(system="rules", user=user)
    assert answer.headline.startswith("Fake analysis: GET /demo/reports")
    assert [o.endpoint for o in answer.observations] == ["GET /demo/reports"]
    assert fake.calls == [("rules", user)]


@pytest.mark.parametrize("user", ["not json", '{"endpoints": []}', "{}"])
async def test_the_fake_still_answers_without_usable_input(user: str) -> None:
    answer = await FakeProvider().complete(system="", user=user)
    assert answer.observations == [] and "Fake analysis" in answer.headline


async def test_the_fake_can_be_made_to_fail() -> None:
    with pytest.raises(ProviderError) as caught:
        await FakeProvider(error=ProviderError("timeout")).complete(system="", user="")
    assert caught.value.kind == "timeout"


def settings(**values: Any) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


async def test_the_factory_builds_the_configured_provider() -> None:
    async with httpx2.AsyncClient() as client:
        assert build_provider(settings(), client) is None
        assert isinstance(build_provider(settings(ai_provider="fake"), client), FakeProvider)
        groq_provider = build_provider(settings(ai_provider="groq", ai_api_key=KEY), client)
        gemini_provider = build_provider(
            settings(ai_provider="gemini", ai_api_key=KEY, ai_model="gemini-3.8-flash"), client
        )
    assert isinstance(groq_provider, GroqProvider)
    assert (groq_provider.model, groq_provider.client) == ("openai/gpt-oss-120b", client)
    assert groq_provider.api_key.get_secret_value() == KEY
    assert isinstance(gemini_provider, GeminiProvider)
    assert gemini_provider.model == "gemini-3.8-flash"
