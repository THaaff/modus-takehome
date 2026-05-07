"""Integration tests for the Typer CLI surface.

Uses Typer's `CliRunner` (Click-backed). Tests cover each subcommand, both stdout-mode
and `--output-dir` mode, and error-exit behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vc_audit.cli import app
from vc_audit.models import TriangulatedValuation

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples" / "inputs"
FULL_FIXTURE = EXAMPLES_DIR / "full.json"


@pytest.fixture
def runner() -> CliRunner:
    # Click 8.2+ keeps stderr separate by default.
    return CliRunner()


def test_example_prints_full_fixture(runner: CliRunner) -> None:
    result = runner.invoke(app, ["example"])
    assert result.exit_code == 0
    assert "Atlas Cloud Inc." in result.stdout


def test_methods_returns_three_descriptors(runner: CliRunner) -> None:
    result = runner.invoke(app, ["methods"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert {d["name"] for d in data} == {"comps", "last_round", "dcf"}


def test_value_default_json_to_stdout(runner: CliRunner) -> None:
    result = runner.invoke(app, ["value", "--input", str(FULL_FIXTURE)])
    assert result.exit_code == 0, result.stderr
    valuation = TriangulatedValuation.model_validate_json(result.stdout)
    assert valuation.company.name == "Atlas Cloud Inc."


def test_value_markdown_to_stdout(runner: CliRunner) -> None:
    result = runner.invoke(app, ["value", "--input", str(FULL_FIXTURE), "--format", "markdown"])
    assert result.exit_code == 0, result.stderr
    assert result.stdout.startswith("# VC Audit Report")


def test_value_output_dir_json(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["value", "--input", str(FULL_FIXTURE), "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.stderr
    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1
    valuation = TriangulatedValuation.model_validate_json(json_files[0].read_text())
    assert valuation.company.name == "Atlas Cloud Inc."


def test_value_output_dir_both(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "value",
            "--input",
            str(FULL_FIXTURE),
            "--output-dir",
            str(tmp_path),
            "--format",
            "both",
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert list(tmp_path.glob("*.json"))
    md_files = list(tmp_path.glob("*.md"))
    assert md_files
    assert md_files[0].read_text().startswith("# VC Audit Report")


def test_value_unparseable_input(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    result = runner.invoke(app, ["value", "--input", str(bad)])
    assert result.exit_code != 0
    assert "error" in result.stderr.lower()


def test_value_no_applicable_method(runner: CliRunner, tmp_path: Path) -> None:
    empty_request = tmp_path / "empty.json"
    empty_request.write_text(
        json.dumps({"company": {"name": "Empty Co"}, "as_of_date": "2026-03-31"})
    )
    result = runner.invoke(app, ["value", "--input", str(empty_request)])
    assert result.exit_code == 2
    assert "No registered method applies" in result.stderr
