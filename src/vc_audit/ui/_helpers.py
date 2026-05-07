"""Pure helpers for the Streamlit demo UI.

Split out from `app.py` so the helpers are unit-testable and importable when the
optional `ui` extra (streamlit) isn't installed. Tests import from here directly.
`app.py` re-exports them for the streamlit page.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from vc_audit.engine import build_default_triangulator
from vc_audit.models import FinancialProjection, TriangulatedValuation, ValuationRequest
from vc_audit.reports import to_markdown_str

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples" / "inputs"

EXAMPLE_FILENAMES: tuple[str, ...] = (
    "comps_only.json",
    "dcf_only.json",
    "full.json",
    "high_dispersion.json",
    "last_round_only.json",
    "with_overrides.json",
)


def load_example(name: str) -> str:
    """Return the JSON text of a bundled fixture in `examples/inputs/`.

    Validates `name` against the known list to avoid path traversal and to fail
    loudly on typos.
    """
    if name not in EXAMPLE_FILENAMES:
        raise FileNotFoundError(
            f"Unknown example fixture: {name!r}. Expected one of: {', '.join(EXAMPLE_FILENAMES)}"
        )
    return (EXAMPLES_DIR / name).read_text(encoding="utf-8")


def form_to_request(form_state: dict[str, Any]) -> ValuationRequest:
    """Build a `ValuationRequest` from a flat form-state dict.

    Floats coming from `st.number_input` widgets are converted via `Decimal(str(v))`
    to preserve the user-visible precision. Empty / None values are dropped so the
    request mirrors the corresponding JSON fixture (omit-not-null) and the engine's
    `is_applicable()` checks behave consistently.
    """
    company: dict[str, Any] = {"name": form_state["company_name"]}
    if form_state.get("company_sector"):
        company["sector"] = form_state["company_sector"]

    payload: dict[str, Any] = {"company": company}

    if form_state.get("revenue") is not None:
        payload["revenue"] = Decimal(str(form_state["revenue"]))
    if form_state.get("ebitda") is not None:
        payload["ebitda"] = Decimal(str(form_state["ebitda"]))

    if form_state.get("last_post_money_valuation") is not None:
        payload["last_post_money_valuation"] = Decimal(str(form_state["last_post_money_valuation"]))
    if form_state.get("last_round_date") is not None:
        payload["last_round_date"] = form_state["last_round_date"]
    if form_state.get("reference_index"):
        payload["reference_index"] = form_state["reference_index"]

    projections_raw = form_state.get("projections") or []
    projections: list[FinancialProjection] = []
    for row in projections_raw:
        if row.get("year") is None or row.get("revenue") is None:
            continue
        projections.append(
            FinancialProjection(
                year=int(row["year"]),
                revenue=Decimal(str(row["revenue"])),
                ebitda=Decimal(str(row.get("ebitda", "0"))),
                capex=Decimal(str(row.get("capex", "0"))),
                change_in_nwc=Decimal(str(row.get("change_in_nwc", "0"))),
            )
        )
    if projections:
        payload["projections"] = projections

    if form_state.get("discount_rate") is not None:
        payload["discount_rate"] = Decimal(str(form_state["discount_rate"]))
    if form_state.get("terminal_growth_rate") is not None:
        payload["terminal_growth_rate"] = Decimal(str(form_state["terminal_growth_rate"]))
    if form_state.get("tax_rate") is not None:
        payload["tax_rate"] = Decimal(str(form_state["tax_rate"]))

    weights_raw = form_state.get("method_weights") or {}
    weights: dict[str, Decimal] = {}
    for key, value in weights_raw.items():
        if not key or value is None:
            continue
        # Streamlit's data_editor can hand back strings (typed columns) or floats
        # (number columns). Either way, skip blanks instead of crashing on
        # `Decimal("")`. Pydantic surfaces a clean error if the value is bogus.
        text = str(value).strip()
        if not text:
            continue
        try:
            weights[str(key)] = Decimal(text)
        except InvalidOperation as e:
            raise ValueError(f"Weight for {key!r} is not a number: {value!r}") from e
    if weights:
        payload["method_weights"] = weights

    if form_state.get("as_of_date") is not None:
        payload["as_of_date"] = form_state["as_of_date"]

    return ValuationRequest.model_validate(payload)


def run(request: ValuationRequest) -> tuple[TriangulatedValuation, str]:
    """Run the default triangulator and return `(valuation, markdown_text)`."""
    valuation = build_default_triangulator().value(request)
    return valuation, to_markdown_str(valuation)
