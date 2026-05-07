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


def test_form_to_request_ignores_blank_weight_cells() -> None:
    """`st.data_editor` returns "" for cleared cells and stringy floats for
    text-typed columns; both should be tolerated. A row with just whitespace is
    treated as "leave this method on auto weighting" rather than a parse error.
    """
    form_state: dict[str, object] = {
        "company_name": "Demo Co",
        "company_sector": None,
        "revenue": 100.0,
        "ebitda": 10.0,
        "last_post_money_valuation": None,
        "last_round_date": None,
        "reference_index": None,
        "projections": [],
        "discount_rate": None,
        "terminal_growth_rate": None,
        "tax_rate": None,
        "as_of_date": date(2026, 5, 7),
        "method_weights": {"comps": ".6", "dcf": 0.4, "last_round": "  "},
    }
    request = form_to_request(form_state)
    assert request.method_weights == {"comps": Decimal("0.6"), "dcf": Decimal("0.4")}


def test_form_to_request_rejects_non_numeric_weight() -> None:
    form_state: dict[str, object] = {
        "company_name": "Demo Co",
        "company_sector": None,
        "revenue": 100.0,
        "ebitda": 10.0,
        "last_post_money_valuation": None,
        "last_round_date": None,
        "reference_index": None,
        "projections": [],
        "discount_rate": None,
        "terminal_growth_rate": None,
        "tax_rate": None,
        "as_of_date": date(2026, 5, 7),
        "method_weights": {"comps": "abc"},
    }
    with pytest.raises(ValueError, match="not a number"):
        form_to_request(form_state)


def test_run_returns_valuation_and_markdown() -> None:
    raw = FULL_FIXTURE.read_text(encoding="utf-8")
    request = ValuationRequest.model_validate_json(raw)
    valuation, markdown_text = run(request)
    assert valuation.point_estimate > Decimal(0)
    assert request.company.name in markdown_text
    assert markdown_text.startswith("# VC Audit Report")


# ---------- Page integration (skips when streamlit isn't installed) ----------

APP_PATH = str(PROJECT_ROOT / "src" / "vc_audit" / "ui" / "app.py")


def _app_test() -> object:
    """Return a freshly initialized AppTest instance, or skip if streamlit is missing.

    Lives outside the test functions so the import-skip happens once per test rather
    than at module import time (which would skip every test in this file).
    """
    testing = pytest.importorskip(
        "streamlit.testing.v1", reason="streamlit (the ui extra) not installed"
    )
    return testing.AppTest.from_file(APP_PATH, default_timeout=30).run()


def test_form_mode_with_defaults_runs_cleanly() -> None:
    """Regression: clicking Run with Form-mode defaults should produce a markdown
    report. Previously the form-submit/Run two-step pattern dropped the request on
    the second rerun and surfaced a non-descriptive 'No valid request to run' error.
    """
    at = _app_test()
    at.radio[0].set_value("Form").run()  # type: ignore[attr-defined]
    run_btn = next(b for b in at.button if b.label == "Run")  # type: ignore[attr-defined]
    assert not run_btn.disabled, "Run should be enabled when defaults are valid"
    run_btn.click().run()
    assert not at.error, [e.value for e in at.error]  # type: ignore[attr-defined]
    assert any(
        "VC Audit Report" in m.value
        for m in at.markdown  # type: ignore[attr-defined]
    )


def test_form_mode_invalid_input_surfaces_descriptive_error() -> None:
    """Regression: setting discount_rate to 0 (model requires gt=0) should produce a
    visible Pydantic error mentioning the field, and disable the Run button.
    """
    at = _app_test()
    at.radio[0].set_value("Form").run()  # type: ignore[attr-defined]
    discount = next(
        n
        for n in at.number_input  # type: ignore[attr-defined]
        if n.label == "Discount rate"
    )
    discount.set_value(0.0).run()
    run_btn = next(b for b in at.button if b.label == "Run")  # type: ignore[attr-defined]
    assert run_btn.disabled, "Run should be disabled when validation fails"
    error_text = " ".join(
        e.value
        for e in at.error  # type: ignore[attr-defined]
    )
    assert "discount_rate" in error_text
    assert "greater than 0" in error_text


def test_paste_json_mode_with_placeholder_runs_cleanly() -> None:
    """The default placeholder JSON is a valid minimal request — Run should succeed."""
    at = _app_test()
    at.radio[0].set_value("Paste JSON").run()  # type: ignore[attr-defined]
    run_btn = next(b for b in at.button if b.label == "Run")  # type: ignore[attr-defined]
    assert not run_btn.disabled
    run_btn.click().run()
    assert not at.error, [e.value for e in at.error]  # type: ignore[attr-defined]
    assert any(
        "VC Audit Report" in m.value
        for m in at.markdown  # type: ignore[attr-defined]
    )


def test_load_example_mode_runs_cleanly() -> None:
    """Initial mode is Load example; Run should produce a report immediately."""
    at = _app_test()
    run_btn = next(b for b in at.button if b.label == "Run")  # type: ignore[attr-defined]
    assert not run_btn.disabled
    run_btn.click().run()
    assert not at.error, [e.value for e in at.error]  # type: ignore[attr-defined]
    assert any(
        "VC Audit Report" in m.value
        for m in at.markdown  # type: ignore[attr-defined]
    )
