"""DCFMethod: applicability gates, numeric correctness, and confidence scaling."""

from decimal import Decimal

from vc_audit.methods.dcf import DCFMethod
from vc_audit.models import (
    FinancialProjection,
    PortfolioCompany,
    ValuationRequest,
)

# Tolerance for hand-rolled numeric reference checks. Decimal arithmetic is exact under
# (+, −, ×, /) at default precision (28 digits), but the reference is computed below at
# the same precision, so a tight tolerance is sufficient.
_TOL = Decimal("0.000001")


def _company() -> PortfolioCompany:
    return PortfolioCompany(name="Acme", sector="SaaS")


def _make_request(
    *,
    projections: list[FinancialProjection] | None,
    discount_rate: Decimal | None = Decimal("0.12"),
    terminal_growth_rate: Decimal | None = Decimal("0.03"),
    tax_rate: Decimal = Decimal("0.21"),
) -> ValuationRequest:
    return ValuationRequest(
        company=_company(),
        projections=projections,
        discount_rate=discount_rate,
        terminal_growth_rate=terminal_growth_rate,
        tax_rate=tax_rate,
    )


def _proj(year: int, ebitda: Decimal, capex: Decimal = Decimal("10")) -> FinancialProjection:
    return FinancialProjection(
        year=year,
        revenue=ebitda * Decimal("3"),  # arbitrary but non-zero
        ebitda=ebitda,
        capex=capex,
        change_in_nwc=Decimal(0),
    )


# ---------- Applicability ----------


def test_not_applicable_when_projections_none() -> None:
    req = _make_request(projections=None)
    assert DCFMethod().is_applicable(req) is False


def test_not_applicable_with_one_year() -> None:
    req = _make_request(projections=[_proj(1, Decimal("100"))])
    assert DCFMethod().is_applicable(req) is False


def test_not_applicable_when_discount_rate_missing() -> None:
    req = _make_request(
        projections=[_proj(1, Decimal("100")), _proj(2, Decimal("110"))],
        discount_rate=None,
    )
    assert DCFMethod().is_applicable(req) is False


def test_not_applicable_when_terminal_growth_missing() -> None:
    req = _make_request(
        projections=[_proj(1, Decimal("100")), _proj(2, Decimal("110"))],
        terminal_growth_rate=None,
    )
    assert DCFMethod().is_applicable(req) is False


def test_not_applicable_when_terminal_growth_ge_discount_rate() -> None:
    """Gordon-stability gate: terminal_growth < discount_rate."""
    req = _make_request(
        projections=[_proj(1, Decimal("100")), _proj(2, Decimal("110"))],
        discount_rate=Decimal("0.05"),
        terminal_growth_rate=Decimal("0.05"),
    )
    assert DCFMethod().is_applicable(req) is False
    req2 = _make_request(
        projections=[_proj(1, Decimal("100")), _proj(2, Decimal("110"))],
        discount_rate=Decimal("0.04"),
        terminal_growth_rate=Decimal("0.05"),
    )
    assert DCFMethod().is_applicable(req2) is False


def test_applicable_on_valid_request() -> None:
    req = _make_request(projections=[_proj(1, Decimal("100")), _proj(2, Decimal("110"))])
    assert DCFMethod().is_applicable(req) is True


# ---------- Numeric correctness ----------


def test_numeric_correctness_known_case() -> None:
    """3 years, EBITDA=[100, 110, 121], capex=10, ΔNWC=0, tax=0.21, r=0.12, g=0.03.

    Expected EV computed inline with the same Decimal precision as the implementation.
    """
    tax = Decimal("0.21")
    r = Decimal("0.12")
    g = Decimal("0.03")
    ebitdas = [Decimal("100"), Decimal("110"), Decimal("121")]
    capex = Decimal("10")

    projections = [
        FinancialProjection(
            year=i + 1,
            revenue=ebitda * Decimal("3"),
            ebitda=ebitda,
            capex=capex,
            change_in_nwc=Decimal(0),
        )
        for i, ebitda in enumerate(ebitdas)
    ]

    pv_sum = Decimal(0)
    fcf_final = Decimal(0)
    t_final = 0
    for i, ebitda in enumerate(ebitdas):
        t = i + 1
        fcf = ebitda * (Decimal(1) - tax) - capex
        pv_sum += fcf / ((Decimal(1) + r) ** t)
        fcf_final = fcf
        t_final = t
    tv = fcf_final * (Decimal(1) + g) / (r - g)
    pv_tv = tv / ((Decimal(1) + r) ** t_final)
    expected_ev = pv_sum + pv_tv

    req = ValuationRequest(
        company=_company(),
        projections=projections,
        discount_rate=r,
        terminal_growth_rate=g,
        tax_rate=tax,
    )
    result = DCFMethod().value(req)

    assert abs(result.point_estimate - expected_ev) < _TOL
    assert abs(result.low - expected_ev * Decimal("0.775")) < _TOL
    assert abs(result.high - expected_ev * Decimal("1.225")) < _TOL


def test_terminal_value_shrinks_when_r_minus_g_widens() -> None:
    """Increasing (r − g) reduces the terminal-value contribution to EV."""
    base_projections = [_proj(1, Decimal("100")), _proj(2, Decimal("110"))]
    narrow = ValuationRequest(
        company=_company(),
        projections=base_projections,
        discount_rate=Decimal("0.10"),
        terminal_growth_rate=Decimal("0.03"),  # r-g = 0.07
        tax_rate=Decimal("0.21"),
    )
    wide = ValuationRequest(
        company=_company(),
        projections=base_projections,
        discount_rate=Decimal("0.20"),
        terminal_growth_rate=Decimal("0.06"),  # r-g = 0.14
        tax_rate=Decimal("0.21"),
    )
    method = DCFMethod()
    narrow_ev = method.value(narrow).point_estimate
    wide_ev = method.value(wide).point_estimate
    assert wide_ev < narrow_ev


def test_more_projection_years_increases_confidence_up_to_5() -> None:
    """Confidence is min(1, n/5) × completeness; more years up to 5 raises it."""
    method = DCFMethod()
    short = method.value(
        _make_request(projections=[_proj(1, Decimal("100")), _proj(2, Decimal("110"))])
    ).confidence
    longer = method.value(
        _make_request(
            projections=[
                _proj(1, Decimal("100")),
                _proj(2, Decimal("110")),
                _proj(3, Decimal("121")),
                _proj(4, Decimal("133")),
            ]
        )
    ).confidence
    assert longer > short


# ---------- Confidence scaling ----------


def test_confidence_two_years_full_completeness() -> None:
    """2/5 × 1.0 = 0.4 — all three of revenue/ebitda/capex non-zero per year."""
    req = _make_request(
        projections=[_proj(1, Decimal("100")), _proj(2, Decimal("110"))],
    )
    result = DCFMethod().value(req)
    assert result.confidence == Decimal("2") / Decimal("5")


def test_confidence_five_years_full_completeness_is_one() -> None:
    req = _make_request(
        projections=[_proj(i, Decimal("100") + Decimal(i)) for i in range(1, 6)],
    )
    result = DCFMethod().value(req)
    assert result.confidence == Decimal(1)


def test_confidence_ten_years_capped_at_one() -> None:
    req = _make_request(
        projections=[_proj(i, Decimal("100") + Decimal(i)) for i in range(1, 11)],
    )
    result = DCFMethod().value(req)
    assert result.confidence == Decimal(1)


def test_partial_completeness_drops_confidence() -> None:
    """Zero-revenue across 2 years → 4/6 = 0.6666... completeness, × 2/5."""
    projections = [
        FinancialProjection(
            year=1,
            revenue=Decimal(0),  # missing
            ebitda=Decimal("100"),
            capex=Decimal("10"),
        ),
        FinancialProjection(
            year=2,
            revenue=Decimal(0),  # missing
            ebitda=Decimal("110"),
            capex=Decimal("10"),
        ),
    ]
    req = _make_request(projections=projections)
    result = DCFMethod().value(req)
    expected = (Decimal(2) / Decimal(5)) * (Decimal(4) / Decimal(6))
    assert result.confidence == expected


# ---------- Citations + Assumptions ----------


def test_emits_citation_with_projection_source() -> None:
    req = _make_request(
        projections=[_proj(1, Decimal("100")), _proj(2, Decimal("110"))],
    )
    result = DCFMethod().value(req)
    assert len(result.citations) >= 1
    assert result.citations[0].source == "ValuationRequest:projections"


def test_emits_assumptions_for_rates_and_formula() -> None:
    req = _make_request(
        projections=[_proj(1, Decimal("100")), _proj(2, Decimal("110"))],
    )
    result = DCFMethod().value(req)
    names = {a.name for a in result.assumptions}
    assert "Discount rate" in names
    assert "Terminal growth rate" in names
    assert "Tax rate" in names
    assert "FCF formula" in names
    assert "Range factor" in names
    assert "Confidence formula" in names


def test_default_tax_rate_is_marked_default() -> None:
    """Default tax_rate (0.21) carries 'default; auditor can override' rationale."""
    req = _make_request(
        projections=[_proj(1, Decimal("100")), _proj(2, Decimal("110"))],
    )
    result = DCFMethod().value(req)
    tax_assumption = next(a for a in result.assumptions if a.name == "Tax rate")
    assert "default" in tax_assumption.rationale.lower()


def test_overridden_tax_rate_marked_auditor_supplied() -> None:
    req = _make_request(
        projections=[_proj(1, Decimal("100")), _proj(2, Decimal("110"))],
        tax_rate=Decimal("0.25"),
    )
    result = DCFMethod().value(req)
    tax_assumption = next(a for a in result.assumptions if a.name == "Tax rate")
    assert "auditor-supplied" in tax_assumption.rationale
