"""Domain-model tests: round-trip parity, Decimal precision, defaults, and validation."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from vc_audit.models import (
    Assumption,
    Citation,
    FinancialProjection,
    MethodResult,
    MethodWeight,
    PortfolioCompany,
    TriangulatedValuation,
    ValuationRequest,
)


def _make_request() -> ValuationRequest:
    # All money values are in $M (millions of US dollars), per project convention.
    return ValuationRequest(
        company=PortfolioCompany(name="Basis AI", sector="SaaS"),
        revenue=Decimal("12.50"),
        ebitda=Decimal("2.10"),
        last_post_money_valuation=Decimal("100"),
        last_round_date=date(2025, 6, 1),
        projections=[
            FinancialProjection(
                year=1,
                revenue=Decimal("15.0"),
                ebitda=Decimal("2.5"),
                capex=Decimal("0.5"),
            ),
            FinancialProjection(
                year=2,
                revenue=Decimal("20.0"),
                ebitda=Decimal("3.5"),
                capex=Decimal("0.7"),
                change_in_nwc=Decimal("0.25"),
            ),
        ],
        discount_rate=Decimal("0.15"),
        terminal_growth_rate=Decimal("0.03"),
        method_weights={"comps": Decimal("0.5"), "dcf": Decimal("0.5")},
    )


def _make_triangulated() -> TriangulatedValuation:
    request = _make_request()
    method_results = [
        MethodResult(
            method_name="comps",
            point_estimate=Decimal("85"),
            low=Decimal("70"),
            high=Decimal("100"),
            confidence=Decimal("0.8"),
            assumptions=[Assumption(name="EV/Revenue", value="6.8x", rationale="Sector median.")],
            citations=[
                Citation(
                    source="CompsProvider:mock_universe_v1",
                    description="20 SaaS peers",
                    retrieved_at=datetime(2026, 5, 6, 12, 0, 0),
                )
            ],
        ),
    ]
    return TriangulatedValuation(
        company=request.company,
        as_of_date=request.as_of_date,
        point_estimate=Decimal("85"),
        range_low=Decimal("70"),
        range_high=Decimal("100"),
        dispersion=Decimal("0.353"),
        dispersion_flag=False,
        method_results=method_results,
        weights=[
            MethodWeight(
                method_name="comps",
                raw_confidence=Decimal("0.8"),
                normalized_weight=Decimal("1"),
            ),
        ],
        request=request,
        generated_at=datetime(2026, 5, 6, 12, 0, 0),
    )


# ---------- Round-trip parity ----------


@pytest.mark.parametrize(
    "model",
    [
        PortfolioCompany(name="Basis AI", sector="SaaS"),
        Assumption(name="multiple", value="8.2x", rationale="median"),
        Citation(
            source="x",
            description="y",
            retrieved_at=datetime(2026, 5, 6, 12, 0, 0),
        ),
        FinancialProjection(
            year=1,
            revenue=Decimal("100"),
            ebitda=Decimal("20"),
            capex=Decimal("5"),
        ),
        _make_request(),
        _make_triangulated(),
    ],
)
def test_round_trip_json(model: object) -> None:
    """JSON round-trip preserves equality for every domain model."""
    cls = type(model)
    json_str = model.model_dump_json()  # type: ignore[attr-defined]
    parsed = cls.model_validate_json(json_str)  # type: ignore[attr-defined]
    assert parsed == model


# ---------- Decimal precision ----------


def test_decimal_precision_survives_json_roundtrip() -> None:
    """Long Decimals must not be corrupted via JSON. This is the audit-correctness test."""
    proj = FinancialProjection(
        year=1,
        revenue=Decimal("123456789.123456789012345"),
        ebitda=Decimal("0.0000000001"),
        capex=Decimal("9999999999.9999999999"),
    )
    parsed = FinancialProjection.model_validate_json(proj.model_dump_json())
    assert parsed.revenue == Decimal("123456789.123456789012345")
    assert parsed.ebitda == Decimal("0.0000000001")
    assert parsed.capex == Decimal("9999999999.9999999999")


def test_decimal_serialized_as_string_in_json() -> None:
    """JSON encodes Decimal as a string (not a number) — defends against float rounding."""
    proj = FinancialProjection(
        year=1,
        revenue=Decimal("1.1"),
        ebitda=Decimal("2.2"),
        capex=Decimal("3.3"),
    )
    json_str = proj.model_dump_json()
    assert '"revenue":"1.1"' in json_str
    assert '"ebitda":"2.2"' in json_str
    assert '"capex":"3.3"' in json_str


# ---------- Defaults ----------


def test_financial_projection_change_in_nwc_default() -> None:
    proj = FinancialProjection(
        year=1, revenue=Decimal("1"), ebitda=Decimal("1"), capex=Decimal("1")
    )
    assert proj.change_in_nwc == Decimal(0)


def test_valuation_request_defaults() -> None:
    req = ValuationRequest(company=PortfolioCompany(name="Acme"))
    assert req.tax_rate == Decimal("0.21")
    assert req.reference_index == "NASDAQ"
    assert req.as_of_date == date.today()
    assert req.method_weights is None
    assert req.projections is None


# ---------- Validation ----------


def test_financial_projection_year_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        FinancialProjection(
            year=0,
            revenue=Decimal("1"),
            ebitda=Decimal("1"),
            capex=Decimal("1"),
        )


def test_discount_rate_bounds() -> None:
    company = PortfolioCompany(name="Acme")
    with pytest.raises(ValidationError):
        ValuationRequest(company=company, discount_rate=Decimal("1.5"))
    with pytest.raises(ValidationError):
        ValuationRequest(company=company, discount_rate=Decimal("0"))


def test_terminal_growth_bounds() -> None:
    company = PortfolioCompany(name="Acme")
    with pytest.raises(ValidationError):
        ValuationRequest(company=company, terminal_growth_rate=Decimal("1"))


def test_tax_rate_bounds() -> None:
    company = PortfolioCompany(name="Acme")
    with pytest.raises(ValidationError):
        ValuationRequest(company=company, tax_rate=Decimal("1.0"))
    # 0 is valid (e.g. an early-stage co with NOLs)
    req = ValuationRequest(company=company, tax_rate=Decimal("0"))
    assert req.tax_rate == Decimal(0)


def test_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        MethodResult(
            method_name="x",
            point_estimate=Decimal("1"),
            low=Decimal("1"),
            high=Decimal("1"),
            confidence=Decimal("1.1"),
        )


def test_dispersion_threshold_constant() -> None:
    """The threshold 0.5 is the documented heuristic — see discussion.md §5c."""
    assert TriangulatedValuation.dispersion_threshold() == Decimal("0.5")
