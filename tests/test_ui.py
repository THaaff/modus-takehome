"""Unit tests for the Streamlit UI's pure helpers.

Streamlit's runtime is hard to drive in tests (would require `streamlit.testing`),
so this file covers only the importable, side-effect-free helpers. The streamlit
page integration test is "does `make ui` open and render?" — manual.

Tests import from `vc_audit.ui._helpers`, not `vc_audit.ui.app`, because `app.py`
imports streamlit at module top. The helpers are split into their own module so
they're importable without the optional `ui` extra installed (which is the case
for `make check` / the dev group).
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from vc_audit.models import ValuationRequest
from vc_audit.ui._helpers import (
    EXAMPLE_FILENAMES,
    EXAMPLES_DIR,
    form_to_request,
    load_example,
    run,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FULL_FIXTURE = PROJECT_ROOT / "examples" / "inputs" / "full.json"


@pytest.mark.parametrize("name", EXAMPLE_FILENAMES)
def test_load_example_returns_valid_json(name: str) -> None:
    raw = load_example(name)
    request = ValuationRequest.model_validate_json(raw)
    assert request.company.name


def test_load_example_unknown_raises() -> None:
    with pytest.raises(FileNotFoundError, match="Unknown example fixture"):
        load_example("does_not_exist.json")


def test_examples_dir_matches_filenames() -> None:
    """Belt-and-suspenders: the EXAMPLE_FILENAMES tuple matches what's on disk."""
    actual = {p.name for p in EXAMPLES_DIR.glob("*.json")}
    assert actual == set(EXAMPLE_FILENAMES)


def test_form_to_request_round_trips_full_fixture() -> None:
    """Round-trip property: a form-state dict that mirrors `full.json` produces
    a `ValuationRequest` equal to the one parsed from the raw JSON.

    Compares via `model_dump()` to side-step any frozen-model equality oddities and
    to make field-level diffs legible if the assertion ever fails.
    """
    raw = FULL_FIXTURE.read_text(encoding="utf-8")
    expected = ValuationRequest.model_validate_json(raw)

    fixture = json.loads(raw)
    form_state = {
        "company_name": fixture["company"]["name"],
        "company_sector": fixture["company"]["sector"],
        "revenue": fixture["revenue"],
        "ebitda": fixture["ebitda"],
        "last_post_money_valuation": fixture["last_post_money_valuation"],
        "last_round_date": date.fromisoformat(fixture["last_round_date"]),
        "reference_index": fixture["reference_index"],
        "projections": [
            {
                "year": p["year"],
                "revenue": p["revenue"],
                "ebitda": p["ebitda"],
                "capex": p["capex"],
                "change_in_nwc": p["change_in_nwc"],
            }
            for p in fixture["projections"]
        ],
        "discount_rate": fixture["discount_rate"],
        "terminal_growth_rate": fixture["terminal_growth_rate"],
        "tax_rate": fixture["tax_rate"],
        "as_of_date": date.fromisoformat(fixture["as_of_date"]),
        "method_weights": {},
    }
    actual = form_to_request(form_state)
    assert actual.model_dump() == expected.model_dump()


def test_run_returns_valuation_and_markdown() -> None:
    raw = FULL_FIXTURE.read_text(encoding="utf-8")
    request = ValuationRequest.model_validate_json(raw)
    valuation, markdown_text = run(request)
    assert valuation.point_estimate > Decimal(0)
    assert request.company.name in markdown_text
    assert markdown_text.startswith("# VC Audit Report")
