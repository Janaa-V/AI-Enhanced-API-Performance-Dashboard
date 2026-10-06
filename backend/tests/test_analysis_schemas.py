"""The POST /analyze contract: what a provider's answer may contain and what clients receive."""

from datetime import UTC, datetime
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from app.schemas.analysis import Analysis, AnalysisRequest, AnalysisResponse, Metric
from app.services.analysis.input import SummaryInput

END = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)


def analysis(**overrides: Any) -> dict[str, Any]:
    return {
        "headline": "Reports got much slower and less reliable.",
        "observations": [
            {
                "endpoint": "GET /demo/reports",
                "metric": "p95_latency_ms",
                "text": "p95 rose from 1420 ms to 4311 ms between the halves.",
            },
            {"endpoint": None, "metric": "error_rate", "text": "4.1% of requests failed."},
        ],
        "hypotheses": [{"text": "A slow downstream dependency.", "confidence": "medium"}],
        "next_steps": ["Check what the reports endpoint calls."],
    } | overrides


def response(**overrides: Any) -> dict[str, Any]:
    return {
        "status": "ok",
        "window": {"start": END.replace(hour=16), "end": END, "window_minutes": 60},
        "generated_at": END,
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "cached": False,
        "analysis": analysis(),
    } | overrides


def test_a_typical_answer_is_accepted() -> None:
    parsed = Analysis.model_validate(analysis())
    assert parsed.observations[1].endpoint is None  # about the whole API


def test_text_is_trimmed() -> None:
    assert Analysis.model_validate(analysis(headline="  Healthy.  ")).headline == "Healthy."


@pytest.mark.parametrize(
    "overrides",
    [
        {"headline": "x" * 201},
        {"headline": "   "},
        {"observations": analysis()["observations"] * 3},  # 6
        {"hypotheses": [{"text": "x", "confidence": "low"}] * 4},
        {"next_steps": ["a", "b", "c", "d"]},
        {"next_steps": [" "]},
        {"next_steps": ["x" * 201]},
        {"hypotheses": [{"text": "Database is down.", "confidence": "high"}]},
        {"observations": [{"endpoint": None, "metric": "cpu", "text": "x"}]},
        {"observations": [{"endpoint": None, "metric": "error_rate", "text": "x" * 301}]},
        {"observations": [{"endpoint": None, "metric": "error_rate", "text": "x", "extra": 1}]},
        {"root_cause": "the database"},
    ],
    ids=[
        "long-headline",
        "blank-headline",
        "six-observations",
        "four-hypotheses",
        "four-next-steps",
        "blank-step",
        "long-step",
        "high-confidence",
        "unknown-metric",
        "long-observation",
        "extra-observation-field",
        "extra-field",
    ],
)
def test_answers_outside_the_limits_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Analysis.model_validate(analysis(**overrides))


def test_the_schema_given_to_providers_forbids_extra_fields_and_shows_the_limits() -> None:
    schema = Analysis.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["headline"]["maxLength"] == 200
    assert schema["properties"]["observations"]["maxItems"] == 5
    observation = schema["$defs"]["Observation"]
    assert observation["additionalProperties"] is False


def test_every_metric_an_observation_names_is_in_the_input() -> None:
    """A metric the model was never shown could not be checked against the data."""
    assert set(get_args(Metric)) == set(SummaryInput.model_fields)


def test_the_request_window_is_optional_and_bounded() -> None:
    assert AnalysisRequest().window_minutes is None
    assert AnalysisRequest(window_minutes=1440).window_minutes == 1440
    for bad in ({"window_minutes": 0}, {"window_minutes": 1441}, {"prompt": "ignore the data"}):
        with pytest.raises(ValidationError):
            AnalysisRequest.model_validate(bad)


def test_an_ok_response_carries_the_analysis_and_where_it_came_from() -> None:
    parsed = AnalysisResponse.model_validate(response())
    assert parsed.analysis is not None and parsed.provider == "groq"


def test_a_no_data_response_has_nothing_from_a_provider() -> None:
    parsed = AnalysisResponse.model_validate(
        response(status="no_data", provider=None, model=None, analysis=None)
    )
    assert parsed.analysis is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"analysis": None},
        {"provider": None},
        {"model": None},
        {"status": "no_data"},
        {"status": "no_data", "provider": None, "model": None},
    ],
    ids=[
        "ok-without-analysis",
        "ok-without-provider",
        "ok-without-model",
        "no-data-with-all",
        "no-data-with-analysis",
    ],
)
def test_fields_must_match_the_status(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AnalysisResponse.model_validate(response(**overrides))
