"""Discounted Cash Flow valuation method.

Pure-math method that operates on the request's `projections`. After-tax FCF per
projection year is discounted at `discount_rate`; a Gordon-growth terminal value at
end-of-horizon is discounted back as well. Enterprise value is the sum.

The ±22.5% range is a placeholder for the T15 sensitivity grid; see Assumption.

D&A tax shield is not modeled — slightly conservative (true after-tax FCF is a touch
higher when D&A is non-trivial). Documented as an Assumption.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar

from vc_audit.methods.base import ValuationMethod
from vc_audit.models import (
    Assumption,
    Citation,
    FinancialProjection,
    MethodResult,
    ValuationRequest,
)

# ±22.5% midpoint range placeholder — replaced in T15 by 3×3 sensitivity grid.
_RANGE_LOW_FACTOR = Decimal("0.775")
_RANGE_HIGH_FACTOR = Decimal("1.225")
# Confidence saturates at 5 projection years.
_CONFIDENCE_SATURATION_YEARS = Decimal("5")


class DCFMethod(ValuationMethod):
    """Discounted Cash Flow valuation.

    Applicability requires at least 2 projection years, both rates set, and
    `terminal_growth_rate < discount_rate` (Gordon-model stability).

    Confidence: `min(1, n_years / 5) × completeness_ratio`, where completeness counts
    non-zero values across `revenue`, `ebitda`, `capex` for each projection year. (We
    treat `change_in_nwc == 0` as populated by default since it has a default of 0.)
    """

    name: ClassVar[str] = "dcf"

    def is_applicable(self, request: ValuationRequest) -> bool:
        if request.projections is None or len(request.projections) < 2:
            return False
        if request.discount_rate is None or request.terminal_growth_rate is None:
            return False
        # Gordon stability — also avoids division by zero/negative on (r - g).
        return request.terminal_growth_rate < request.discount_rate

    def value(self, request: ValuationRequest) -> MethodResult:
        # Caller is responsible for is_applicable; assert the invariants we relied on.
        assert request.projections is not None
        assert request.discount_rate is not None
        assert request.terminal_growth_rate is not None

        projections = sorted(request.projections, key=lambda p: p.year)
        r = request.discount_rate
        g = request.terminal_growth_rate
        tax = request.tax_rate
        n_years = len(projections)

        # Step 1+2: per-year after-tax FCF discounted to PV.
        pv_sum = Decimal(0)
        fcf_final = Decimal(0)
        t_final = 0
        for proj in projections:
            fcf = self._fcf(proj, tax)
            discount = (Decimal(1) + r) ** proj.year
            pv_sum += fcf / discount
            fcf_final = fcf
            t_final = proj.year

        # Step 3: Gordon-growth terminal value at end of horizon, then discount back.
        terminal_value = fcf_final * (Decimal(1) + g) / (r - g)
        pv_terminal = terminal_value / ((Decimal(1) + r) ** t_final)

        # Step 4: enterprise value.
        ev = pv_sum + pv_terminal

        # Step 5: range ±22.5% around the point estimate.
        low = ev * _RANGE_LOW_FACTOR
        high = ev * _RANGE_HIGH_FACTOR

        # Step 6: confidence — horizon coverage × completeness.
        years_factor = min(Decimal(1), Decimal(n_years) / _CONFIDENCE_SATURATION_YEARS)
        completeness = self._completeness_ratio(projections)
        confidence = years_factor * completeness

        assumptions = self._build_assumptions(request, n_years)
        citations = [
            Citation(
                source="ValuationRequest:projections",
                description=(
                    f"DCF on {n_years} projection years; "
                    f"discount={r}, terminal_growth={g}, tax={tax}"
                ),
                retrieved_at=datetime.now(UTC),
                url=None,
            )
        ]

        return MethodResult(
            method_name=self.name,
            point_estimate=ev,
            low=low,
            high=high,
            confidence=confidence,
            assumptions=assumptions,
            citations=citations,
            notes=(
                f"Sum of {n_years} discounted FCFs plus Gordon terminal "
                f"(g={g}) discounted at r={r}."
            ),
        )

    @staticmethod
    def _fcf(proj: FinancialProjection, tax: Decimal) -> Decimal:
        """After-tax FCF = EBITDA × (1 − tax) − capex − ΔNWC. No D&A tax shield."""
        return proj.ebitda * (Decimal(1) - tax) - proj.capex - proj.change_in_nwc

    @staticmethod
    def _completeness_ratio(projections: list[FinancialProjection]) -> Decimal:
        """Fraction of expected (revenue, ebitda, capex) fields populated across years.

        ΔNWC is excluded from the denominator: it has a default of 0, so a "0" value
        cannot be distinguished from "missing" anyway.
        """
        n_years = len(projections)
        if n_years == 0:
            return Decimal(0)
        expected = Decimal(3 * n_years)  # revenue, ebitda, capex per year
        populated = Decimal(0)
        for proj in projections:
            if proj.revenue != 0:
                populated += 1
            if proj.ebitda != 0:
                populated += 1
            if proj.capex != 0:
                populated += 1
        return populated / expected

    @staticmethod
    def _build_assumptions(request: ValuationRequest, n_years: int) -> list[Assumption]:
        assert request.discount_rate is not None
        assert request.terminal_growth_rate is not None
        tax_rationale = (
            "default; auditor can override"
            if request.tax_rate == Decimal("0.21")
            else "auditor-supplied"
        )
        return [
            Assumption(
                name="Discount rate",
                value=str(request.discount_rate),
                rationale="Auditor-supplied WACC proxy.",
            ),
            Assumption(
                name="Terminal growth rate",
                value=str(request.terminal_growth_rate),
                rationale="Long-run nominal growth; must be < discount rate (Gordon stability).",
            ),
            Assumption(
                name="Tax rate",
                value=str(request.tax_rate),
                rationale=tax_rationale,
            ),
            Assumption(
                name="FCF formula",
                value="EBITDA × (1 − tax) − capex − ΔNWC",
                rationale="No D&A tax shield modeled — slightly conservative.",
            ),
            Assumption(
                name="Range factor",
                value="±22.5%",
                rationale=(
                    "Placeholder for T15 sensitivity grid; will be replaced by "
                    "3×3 (discount_rate ± 1pp × terminal_growth ± 0.5pp) in Phase 3."
                ),
            ),
            Assumption(
                name="Confidence formula",
                value=f"min(1, {n_years}/5) × completeness_ratio",
                rationale=(
                    "Saturates at 5 projection years; completeness counts non-zero "
                    "revenue/ebitda/capex across years (ΔNWC excluded — default is 0)."
                ),
            ),
        ]
