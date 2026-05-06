"""JSON + Markdown report writers: round-trip parity, file I/O, section presence."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from vc_audit.models import (
    Assumption,
    Citation,
    MethodResult,
    MethodWeight,
    PortfolioCompany,
    TriangulatedValuation,
    ValuationRequest,
)
from vc_audit.reports import to_json_str, to_markdown_str, write_json, write_markdown


def _make_valuation(
    *,
    point: Decimal = Decimal("85000000"),
    low: Decimal = Decimal("60000000"),
    high: Decimal = Decimal("110000000"),
    dispersion: Decimal = Decimal("0.588"),
    dispersion_flag: bool = True,
) -> TriangulatedValuation:
    request = ValuationRequest(
        company=PortfolioCompany(name="Basis AI", sector="SaaS"),
        revenue=Decimal("12500000"),
        ebitda=Decimal("2100000"),
        as_of_date=date(2026, 5, 6),
    )
    method_results = [
        MethodResult(
            method_name="comps",
            point_estimate=Decimal("80000000"),
            low=Decimal("60000000"),
            high=Decimal("100000000"),
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
            point_estimate=Decimal("90000000"),
            low=Decimal("70000000"),
            high=Decimal("110000000"),
            confidence=Decimal("0.4"),
            assumptions=[
                Assumption(
                    name="Discount rate",
                    value="0.12",
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
        method_results=method_results,
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
    assert parsed.method_results[0].point_estimate == Decimal("80000000")


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
    # Currency strings — formatter strips trailing zeros after decimal.
    assert "$80,000,000" in md
    assert "$90,000,000" in md


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
