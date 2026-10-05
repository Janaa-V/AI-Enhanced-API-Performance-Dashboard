"""The OpenAPI snapshot the frontend generates its types from."""

import json
from pathlib import Path

import pytest

from scripts import export_openapi


@pytest.fixture
def snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Inside a fake repository root, so the script can print the path relative to it.
    path = tmp_path / "frontend" / "openapi.json"
    path.parent.mkdir()
    monkeypatch.setattr(export_openapi, "BACKEND_ROOT", tmp_path / "backend")
    monkeypatch.setattr(export_openapi, "SNAPSHOT", path)
    return path


def test_writes_the_schema_the_app_serves(snapshot: Path) -> None:
    assert export_openapi.main([]) == 0
    schema = json.loads(snapshot.read_text(encoding="utf-8"))
    assert schema == export_openapi.app.openapi()
    assert "/metrics" in schema["paths"]


def test_check_passes_when_the_snapshot_is_current(snapshot: Path) -> None:
    export_openapi.main([])
    assert export_openapi.main(["--check"]) == 0


@pytest.mark.parametrize("content", [None, "{}\n"], ids=["missing", "stale"])
def test_check_fails_without_writing_when_the_snapshot_is_out_of_date(
    snapshot: Path, content: str | None, capsys: pytest.CaptureFixture[str]
) -> None:
    if content is not None:
        snapshot.write_text(content, encoding="utf-8")
    assert export_openapi.main(["--check"]) == 1
    assert "make openapi" in capsys.readouterr().err
    assert (snapshot.read_text(encoding="utf-8") if snapshot.exists() else None) == content
