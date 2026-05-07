"""Streamlit demo UI.

Runs the engine **in-process**: imports `build_default_triangulator()` directly and
executes triangulation in the Streamlit Python process. No HTTP roundtrip — the
FastAPI app still exists for the integration-shape demo.

Layout: title -> input mode (`Load example | Form | Paste JSON`) -> Run button ->
markdown report + raw JSON expander. Sidebar links to `/docs` and `examples/inputs/`.

Pure logic (form -> request, fixture loader, engine call) lives in `_helpers.py` so
it's importable and unit-testable without streamlit installed. This module is the
streamlit-only entry point — `streamlit run src/vc_audit/ui/app.py` executes it.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import streamlit as st  # type: ignore[import-not-found, unused-ignore]
from pydantic import ValidationError

from vc_audit.methods import NoApplicableMethodError
from vc_audit.models import ValuationRequest
from vc_audit.reports import to_json_str
from vc_audit.ui._helpers import EXAMPLE_FILENAMES, form_to_request, load_example, run


def _render_load_example() -> tuple[ValuationRequest | None, str | None]:
    selected = st.selectbox("Choose a fixture", options=list(EXAMPLE_FILENAMES))
    raw = load_example(selected)
    st.code(raw, language="json")
    try:
        return ValuationRequest.model_validate_json(raw), None
    except ValidationError as e:
        return None, f"Failed to parse fixture: {e}"


def _render_form() -> tuple[ValuationRequest | None, str | None]:
    with st.expander("Company", expanded=True):
        company_name = st.text_input("Name", value="Atlas Cloud Inc.")
        company_sector = st.text_input("Sector", value="SaaS")

    with st.expander("Comps inputs"):
        revenue = st.number_input("Revenue ($M)", value=500.0, step=10.0, format="%.2f")
        ebitda = st.number_input("EBITDA ($M)", value=75.0, step=5.0, format="%.2f")

    with st.expander("Last round inputs"):
        last_post_money_valuation = st.number_input(
            "Last post-money valuation ($M)", value=4500.0, step=100.0, format="%.2f"
        )
        last_round_date = st.date_input("Last round date", value=date(2023, 9, 29))
        reference_index = st.text_input("Reference index", value="NASDAQ")

    with st.expander("DCF inputs"):
        default_projections = [
            {
                "year": y,
                "revenue": rev,
                "ebitda": eb,
                "capex": capex,
                "change_in_nwc": nwc,
            }
            for y, rev, eb, capex, nwc in [
                (1, 600.0, 100.0, 30.0, 10.0),
                (2, 720.0, 130.0, 35.0, 12.0),
                (3, 850.0, 160.0, 40.0, 14.0),
                (4, 970.0, 185.0, 45.0, 15.0),
                (5, 1080.0, 210.0, 50.0, 16.0),
            ]
        ]
        projections_table = st.data_editor(
            default_projections, num_rows="dynamic", key="projections_editor"
        )
        discount_rate = st.number_input(
            "Discount rate", min_value=0.0, max_value=0.99, value=0.12, step=0.01
        )
        terminal_growth_rate = st.number_input(
            "Terminal growth rate", min_value=0.0, max_value=0.99, value=0.03, step=0.005
        )
        tax_rate = st.number_input("Tax rate", min_value=0.0, max_value=0.99, value=0.21, step=0.01)

    with st.expander("Auditor controls"):
        as_of_date = st.date_input("As-of date", value=date.today())
        default_weights = [
            {"method": "comps", "weight": None},
            {"method": "dcf", "weight": None},
            {"method": "last_round", "weight": None},
        ]
        weights_table = st.data_editor(
            default_weights,
            num_rows="dynamic",
            key="weights_editor",
            column_config={
                "method": st.column_config.TextColumn(
                    "method",
                    help="Method name to override (comps, dcf, last_round).",
                ),
                "weight": st.column_config.NumberColumn(
                    "weight",
                    help="Override weight in [0, 1]. Leave blank to keep auto weighting.",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                    format="%.4f",
                ),
            },
        )

    weights = {
        row["method"]: row["weight"]
        for row in (weights_table or [])
        if row.get("method") and row.get("weight") is not None
    }

    form_state: dict[str, Any] = {
        "company_name": company_name,
        "company_sector": company_sector or None,
        "revenue": revenue,
        "ebitda": ebitda,
        "last_post_money_valuation": last_post_money_valuation,
        "last_round_date": last_round_date,
        "reference_index": reference_index,
        "projections": projections_table,
        "discount_rate": discount_rate,
        "terminal_growth_rate": terminal_growth_rate,
        "tax_rate": tax_rate,
        "as_of_date": as_of_date,
        "method_weights": weights,
    }
    try:
        return form_to_request(form_state), None
    except ValidationError as e:
        return None, f"Validation error: {e}"
    except ValueError as e:
        return None, f"Form input error: {e}"


def _render_paste_json() -> tuple[ValuationRequest | None, str | None]:
    placeholder = json.dumps(
        {
            "company": {"name": "Demo Co", "sector": "SaaS"},
            "revenue": "100.0",
            "ebitda": "10.0",
            "as_of_date": str(date.today()),
        },
        indent=2,
    )
    text = st.text_area("Request JSON", value=placeholder, height=300)
    if not text.strip():
        return None, None
    try:
        return ValuationRequest.model_validate_json(text), None
    except ValidationError as e:
        return None, f"Validation error: {e}"
    except ValueError as e:
        return None, f"Failed to parse JSON: {e}"


st.set_page_config(page_title="VC Audit Tool", layout="wide")
st.title("VC Audit Tool")
st.write(
    "Multi-method fair-value triangulation for private VC portfolio companies. "
    "Pick an input mode, hit **Run**, and you'll get a triangulated point estimate, "
    "a per-method breakdown with assumptions and citations, and the raw JSON "
    "artifact for the audit trail."
)

with st.sidebar:
    st.markdown("**Other surfaces**")
    st.markdown(
        "- [API docs](http://localhost:8000/docs) (run `make dev`)\n"
        "- CLI: `uv run vc-audit value -i examples/inputs/full.json`\n"
        "- Bundled fixtures live under `examples/inputs/`"
    )

mode = st.radio(
    "Input mode",
    options=("Load example", "Form", "Paste JSON"),
    horizontal=True,
)

request: ValuationRequest | None
error_message: str | None

if mode == "Load example":
    request, error_message = _render_load_example()
elif mode == "Form":
    request, error_message = _render_form()
else:
    request, error_message = _render_paste_json()

if error_message:
    st.error(error_message)

if st.button("Run", type="primary", disabled=request is None):
    if request is None:
        st.error("No valid request to run. Fix the errors above.")
    else:
        try:
            valuation, markdown_text = run(request)
        except NoApplicableMethodError as e:
            st.error(f"No applicable method: {e}")
        except ValueError as e:
            st.error(f"Engine error: {e}")
        else:
            # Streamlit's markdown renders `$...$` as KaTeX inline math, which
            # silently mangles paired currency values like `$48.71M – $2,072.50M`
            # into half-large math text. Escape to render dollars literally.
            st.markdown(markdown_text.replace("$", r"\$"))
            with st.expander("Raw JSON artifact"):
                st.json(json.loads(to_json_str(valuation)))
