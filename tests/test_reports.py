"""JSON + Markdown report writers: round-trip parity, file I/O, section presence."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from vc_audit.models import (
    Assumption,
    Citation,
    DCFSensitivityCell,
    DCFSensitivityGrid,
    MethodResult,
    MethodWeight,
    PortfolioCompany,
    SkippedMethod,
    TriangulatedValuation,
    ValuationRequest,
)
from vc_audit.reports import to_json_str, to_markdown_str, write_json, write_markdown


def _make_valuation(
    *,
    point: Decimal = Decimal("85"),
    low: Decimal = Decimal("60"),
    high: Decimal = Decimal("110"),
    dispersion: Decimal = Decimal("0.588"),
    dispersion_flag: bool = True,
    outlier_method_names: list[str] | None = None,
    skipped_methods: list[SkippedMethod] | None = None,
) -> TriangulatedValuation:
    # All money values are in $M (millions of US dollars), per project convention.
    request = ValuationRequest(
        company=PortfolioCompany(name="Basis AI", sector="SaaS"),
        revenue=Decimal("12.5"),
        ebitda=Decimal("2.1"),
        as_of_date=date(2026, 5, 6),
    )
    method_results = [
        MethodResult(
            method_name="comps",
            point_estimate=Decimal("80"),
            low=Decimal("60"),
            high=Decimal("100"),
            confidence=Decimal("0.6"),
            assumptions=[Assumption(name="EV/Revenue", value="6.4x", rationale="Sector median.")],
            citations=[
                Citation(
                    source="CompsProvider:mock_universe_v1",
                    description="20 SaaS peers",
                    retrieved_at=datetime(2026, 5, 6, 12, 0, 0, tzinfo=UTC),
                )
            ],
            notes="Comps-based EV estimate.",
        ),
        MethodResult(
            method_name="dcf",
            point_estimate=Decimal("90"),
            low=Decimal("70"),
            high=Decimal("110"),
            confidence=Decimal("0.4"),
            assumptions=[
                Assumption(
                    name="Discount rate",
                    value="12.00%",
                    rationale="Auditor-supplied.",
                )
            ],
            citations=[
                Citation(
                    source="ValuationRequest:projections",
                    description="DCF on 3 years",
                    retrieved_at=datetime(2026, 5, 6, 12, 0, 0, tzinfo=UTC),
                )
            ],
            notes="DCF estimate.",
        ),
    ]
    weights = [
        MethodWeight(
            method_name="comps",
            raw_confidence=Decimal("0.6"),
            normalized_weight=Decimal("0.6"),
        ),
        MethodWeight(
            method_name="dcf",
            raw_confidence=Decimal("0.4"),
            normalized_weight=Decimal("0.4"),
        ),
    ]
    return TriangulatedValuation(
        company=request.company,
        as_of_date=request.as_of_date,
        point_estimate=point,
        range_low=low,
        range_high=high,
        dispersion=dispersion,
        dispersion_flag=dispersion_flag,
        outlier_method_names=outlier_method_names or [],
        method_results=method_results,
        skipped_methods=skipped_methods or [],
        weights=weights,
        request=request,
        generated_at=datetime(2026, 5, 6, 12, 0, 0, tzinfo=UTC),
    )


# ---------- JSON ----------


def test_json_round_trip_preserves_decimals() -> None:
    valuation = _make_valuation()
    json_str = to_json_str(valuation)
    parsed = TriangulatedValuation.model_validate_json(json_str)
    assert parsed == valuation
    # Spot-check Decimal precision
    assert parsed.point_estimate == valuation.point_estimate
    assert parsed.dispersion == valuation.dispersion
    assert parsed.method_results[0].point_estimate == Decimal("80")


def test_write_json_writes_round_trippable_file(tmp_path: Path) -> None:
    valuation = _make_valuation()
    target = tmp_path / "report.json"
    returned = write_json(valuation, target)
    assert returned == target
    assert target.exists()
    parsed = TriangulatedValuation.model_validate_json(target.read_text(encoding="utf-8"))
    assert parsed == valuation


# ---------- Markdown ----------


def test_markdown_contains_expected_sections() -> None:
    valuation = _make_valuation()
    md = to_markdown_str(valuation)
    assert "# VC Audit Report" in md
    assert "## Headline" in md
    assert "## Method breakdown" in md
    assert "## Request" in md


def test_markdown_dispersion_flag_marker_when_flagged() -> None:
    flagged = _make_valuation(dispersion=Decimal("0.6"), dispersion_flag=True)
    md = to_markdown_str(flagged)
    assert "(FLAG)" in md
    assert "(within tolerance)" not in md


def test_markdown_dispersion_marker_when_within_tolerance() -> None:
    ok = _make_valuation(dispersion=Decimal("0.3"), dispersion_flag=False)
    md = to_markdown_str(ok)
    assert "(within tolerance)" in md
    assert "(FLAG)" not in md


def test_markdown_contains_each_method_name_and_point_estimate() -> None:
    valuation = _make_valuation()
    md = to_markdown_str(valuation)
    for result in valuation.method_results:
        assert result.method_name in md
    # Currency strings — values are in $M, always rendered with 2dp + M suffix.
    assert "$80.00M" in md
    assert "$90.00M" in md


def test_write_markdown_matches_to_markdown_str(tmp_path: Path) -> None:
    valuation = _make_valuation()
    target = tmp_path / "report.md"
    returned = write_markdown(valuation, target)
    assert returned == target
    assert target.exists()
    assert target.read_text(encoding="utf-8") == to_markdown_str(valuation)


def test_markdown_includes_request_appendix_with_company_name() -> None:
    valuation = _make_valuation()
    md = to_markdown_str(valuation)
    # Echoed request body should include the company name.
    assert "Basis AI" in md
    # And a fenced JSON block.
    assert "```json" in md


def test_markdown_lists_outliers_in_headline() -> None:
    valuation = _make_valuation(outlier_method_names=["dcf"])
    md = to_markdown_str(valuation)
    assert "**Outlier methods:** dcf" in md


def test_markdown_omits_outlier_line_when_empty() -> None:
    valuation = _make_valuation(outlier_method_names=[])
    md = to_markdown_str(valuation)
    assert "Outlier methods:" not in md


def test_markdown_renders_skipped_methods_section() -> None:
    valuation = _make_valuation(
        skipped_methods=[
            SkippedMethod(method_name="dcf", reason="No projections supplied."),
            SkippedMethod(method_name="last_round", reason="No prior round."),
        ]
    )
    md = to_markdown_str(valuation)
    assert "## Skipped methods" in md
    assert "**dcf:** No projections supplied." in md
    assert "**last_round:** No prior round." in md


def test_markdown_omits_skipped_methods_section_when_none() -> None:
    valuation = _make_valuation(skipped_methods=[])
    md = to_markdown_str(valuation)
    assert "## Skipped methods" not in md


def _make_grid(*, all_valid: bool = True) -> DCFSensitivityGrid:
    """Build a 3x3 grid for rendering tests. When all_valid=False, the (-1pp, +0.5pp)
    cell is marked skipped to exercise the "— (skipped)" path."""
    rates = [Decimal("0.11"), Decimal("0.12"), Decimal("0.13")]
    growths = [Decimal("0.025"), Decimal("0.03"), Decimal("0.035")]
    cells: list[DCFSensitivityCell] = []
    for r in rates:
        for g in growths:
            if not all_valid and r == Decimal("0.11") and g == Decimal("0.035"):
                cells.append(
                    DCFSensitivityCell(
                        discount_rate=r,
                        terminal_growth=g,
                        enterprise_value=None,
                        skipped_reason="Gordon stability: g >= r",
                    )
                )
            else:
                cells.append(
                    DCFSensitivityCell(
                        discount_rate=r,
                        terminal_growth=g,
                        enterprise_value=Decimal("100") + Decimal(rates.index(r) * 3),
                    )
                )
    return DCFSensitivityGrid(
        center_discount_rate=Decimal("0.12"),
        center_terminal_growth=Decimal("0.03"),
        discount_rate_deltas=[Decimal("-0.01"), Decimal("0"), Decimal("0.01")],
        terminal_growth_deltas=[Decimal("-0.005"), Decimal("0"), Decimal("0.005")],
        cells=cells,
        skipped_count=0 if all_valid else 1,
    )


def test_markdown_renders_dcf_sensitivity_grid_when_present() -> None:
    """When MethodResult carries a dcf_sensitivity, the markdown shows the table."""
    valuation = _make_valuation()
    valuation.method_results[1].dcf_sensitivity = _make_grid()
    md = to_markdown_str(valuation)
    assert "Sensitivity grid (EV in $M):" in md
    # Header advertises perturbed terminal-growth columns at center ±0.5pp.
    assert "discount rate \\ terminal growth" in md
    # The center cell value is bolded.
    assert "**$103.00M**" in md
    # Row header for the perturbed discount rate (12.00%) is rendered.
    assert "| 12.00% |" in md


def test_markdown_grid_marks_skipped_cells() -> None:
    """A skipped cell renders as `— (skipped)` rather than a dollar value."""
    valuation = _make_valuation()
    valuation.method_results[1].dcf_sensitivity = _make_grid(all_valid=False)
    md = to_markdown_str(valuation)
    assert "— (skipped)" in md


def test_markdown_omits_grid_block_when_no_sensitivity() -> None:
    """Methods without dcf_sensitivity (e.g. comps) shouldn't render the grid block."""
    valuation = _make_valuation()
    # Default valuation has no dcf_sensitivity on either method result.
    md = to_markdown_str(valuation)
    assert "Sensitivity grid (EV in $M):" not in md


def test_markdown_table_has_outlier_column() -> None:
    valuation = _make_valuation(outlier_method_names=["dcf"])
    md = to_markdown_str(valuation)
    # Header carries the new column.
    assert "Outlier" in md
    lines = md.splitlines()
    comps_row = next(line for line in lines if line.startswith("| comps "))
    dcf_row = next(line for line in lines if line.startswith("| dcf "))
    assert dcf_row.rstrip().endswith("| yes |")
    assert comps_row.rstrip().endswith("|  |")
