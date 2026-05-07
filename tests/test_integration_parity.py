"""End-to-end parity check: CLI and API produce equal valuations for the same input.

Excludes timestamps (`generated_at` and per-citation `retrieved_at`) — these record
when the valuation was run, not what was computed, so they're expected to differ
between two separate runs. Everything else — the point estimate, range, dispersion,
per-method results, weights, and echoed request — must match exactly. Confirms the
two presentation surfaces are paper-thin wrappers over a single engine.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from vc_audit.api import app as api_app
from vc_audit.cli import app as cli_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FULL_FIXTURE = PROJECT_ROOT / "examples" / "inputs" / "full.json"


def test_cli_and_api_produce_identical_valuations() -> None:
    body = json.loads(FULL_FIXTURE.read_text())

    api_client = TestClient(api_app)
    api_resp = api_client.post("/valuations", json=body)
    assert api_resp.status_code == 200
    api_payload = api_resp.json()

    cli_runner = CliRunner()
    cli_result = cli_runner.invoke(cli_app, ["value", "--input", str(FULL_FIXTURE)])
    assert cli_result.exit_code == 0, cli_result.stderr
    cli_payload = json.loads(cli_result.stdout)

    _strip_timestamps(api_payload)
    _strip_timestamps(cli_payload)

    assert api_payload == cli_payload


def _strip_timestamps(payload: dict[str, object]) -> None:
    """Remove fields that record run-time, not run-output: `generated_at` + every
    citation's `retrieved_at`. We compare what was *computed*, not when."""
    payload.pop("generated_at", None)
    method_results = payload.get("method_results")
    if isinstance(method_results, list):
        for result in method_results:
            assert isinstance(result, dict)
            for citation in result.get("citations", []):
                assert isinstance(citation, dict)
                citation.pop("retrieved_at", None)
