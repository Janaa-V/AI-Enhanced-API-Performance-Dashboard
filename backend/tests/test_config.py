"""Verify the test-database setting can be changed through the environment or .env."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


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
