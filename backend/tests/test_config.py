"""Verify the test-database setting can be changed through the environment or .env."""

from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.services.simulation import DEFAULT_PROFILES


def test_test_database_name_has_a_safe_default() -> None:
    assert Settings(_env_file=None).test_db_name == "performance_dashboard_test"


def test_test_database_name_can_be_set_in_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_DB_NAME", "custom_test")
    assert Settings(_env_file=None).test_db_name == "custom_test"


def test_test_database_name_can_be_set_in_an_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_DB_NAME=from_file_test\n")
    assert Settings(_env_file=env_file).test_db_name == "from_file_test"


def test_simulation_settings_default_to_normal_behaviour() -> None:
    settings = Settings(_env_file=None)
    assert settings.simulation_latency_scale == 1
    assert settings.simulation_failure_scale == 1


@pytest.mark.parametrize("name", ["simulation_latency_scale", "simulation_failure_scale"])
def test_negative_simulation_scales_are_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{name: -1})


def test_no_endpoint_is_degraded_by_default() -> None:
    assert Settings(_env_file=None).simulation_degraded_endpoint is None


def test_the_degraded_endpoint_can_be_set_in_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIMULATION_DEGRADED_ENDPOINT", "reports")
    assert Settings(_env_file=None).simulation_degraded_endpoint == "reports"


def test_an_unknown_degraded_endpoint_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, simulation_degraded_endpoint="report")  # type: ignore[arg-type]


def test_the_degraded_endpoint_choices_match_the_profiles() -> None:
    """A new profile must be added to the setting too, or it could never be degraded."""
    annotation = Settings.model_fields["simulation_degraded_endpoint"].annotation
    literal = next(arg for arg in get_args(annotation) if arg is not type(None))
    assert set(get_args(literal)) == set(DEFAULT_PROFILES)


def test_ai_is_disabled_by_default() -> None:
    assert Settings(_env_file=None).ai_provider == "disabled"


@pytest.mark.parametrize("provider", ["groq", "gemini"])
def test_a_real_provider_needs_a_key(provider: str) -> None:
    with pytest.raises(ValidationError, match="AI_API_KEY"):
        Settings(_env_file=None, ai_provider=provider)  # type: ignore[arg-type]
    assert Settings(_env_file=None, ai_provider=provider, ai_api_key="k").ai_provider == provider  # type: ignore[arg-type]


def test_the_fake_provider_is_refused_in_production() -> None:
    assert Settings(_env_file=None, ai_provider="fake").ai_provider == "fake"
    with pytest.raises(ValidationError, match="not allowed in production"):
        Settings(_env_file=None, ai_provider="fake", environment="production")


@pytest.mark.parametrize(
    "model",
    ["../secrets", "a/../b", ".hidden", "a/b/c", "gemini flash", "a?key=x", "x" * 101],
)
def test_unsafe_model_names_are_rejected(model: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_model=model)


@pytest.mark.parametrize(
    "model", ["", "openai/gpt-oss-120b", "gemini-3.5-flash-lite", "llama-3.3-70b-versatile"]
)
def test_real_model_names_are_accepted(model: str) -> None:
    assert Settings(_env_file=None, ai_model=model).ai_model == model
