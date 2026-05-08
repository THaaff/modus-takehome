"""Discounted Cash Flow valuation method.

Pure-math method that operates on the request's `projections`. After-tax FCF per
projection year is discounted at `discount_rate`; a Gordon-growth terminal value at
end-of-horizon is discounted back as well. Enterprise value is the sum.

The range is derived from a 3x3 sensitivity grid (discount_rate +/- 1pp x
terminal_growth +/- 0.5pp), with min/max across the valid cells as the bounds and
the midpoint of those bounds as the point estimate. Cells where the perturbed
terminal growth meets or exceeds the perturbed discount rate (Gordon instability)
are skipped and surfaced in the assumption rationale.

D&A tax shield is not modeled — slightly conservative (true after-tax FCF is a touch
higher when D&A is non-trivial). Documented as an Assumption.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar

from vc_audit.methods.base import ValuationMethod
from vc_audit.methods.descriptor import MethodDescriptor
from vc_audit.models import (
    Assumption,
    Citation,
    DCFSensitivityCell,
    DCFSensitivityGrid,
    FinancialProjection,
    MethodResult,
    ValuationRequest,
)

# Confidence saturates at 5 projection years.
_CONFIDENCE_SATURATION_YEARS = Decimal("5")

# Sensitivity grid offsets applied to the auditor-supplied rates.
_DISCOUNT_RATE_DELTAS: tuple[Decimal, ...] = (
    Decimal("-0.01"),
    Decimal("0"),
    Decimal("0.01"),
)
_TERMINAL_GROWTH_DELTAS: tuple[Decimal, ...] = (
    Decimal("-0.005"),
    Decimal("0"),
    Decimal("0.005"),
)


def _format_rate(rate: Decimal) -> str:
    """Render an annual rate (e.g., 0.12) as ``12.00%`` for assumption display.

    The ``%`` suffix disambiguates from raw decimals; ``per annum`` is implicit in
    the assumption name (Discount rate, Terminal growth rate, Tax rate).
    """
    return f"{(rate * 100).quantize(Decimal('0.01')):f}%"


def _compute_ev(
    projections: list[FinancialProjection],
    r: Decimal,
    g: Decimal,
    tax: Decimal,
) -> Decimal:
    """Single-cell DCF: PV of per-year FCFs plus discounted Gordon terminal value.

    Caller must ensure ``g < r`` (Gordon stability); this helper does no guarding.
    """
    pv_sum = Decimal(0)
    fcf_final = Decimal(0)
    t_final = 0
    for proj in projections:
        fcf = proj.ebitda * (Decimal(1) - tax) - proj.capex - proj.change_in_nwc
        pv_sum += fcf / ((Decimal(1) + r) ** proj.year)
        fcf_final = fcf
        t_final = proj.year
    terminal_value = fcf_final * (Decimal(1) + g) / (r - g)
    pv_terminal = terminal_value / ((Decimal(1) + r) ** t_final)
    return pv_sum + pv_terminal


_GORDON_SKIP_REASON = "Gordon stability: g >= r"


def _run_sensitivity_grid(
    projections: list[FinancialProjection],
    r: Decimal,
    g: Decimal,
    tax: Decimal,
) -> list[DCFSensitivityCell]:
    """Compute the full 3x3 grid as typed cells.

    Cells are emitted in row-major order: outer loop over discount-rate deltas,
    inner over terminal-growth deltas. Cells that violate Gordon stability
    (``g_p >= r_p``) are returned with ``enterprise_value=None`` and a
    ``skipped_reason``, so callers can preserve the full grid shape rather than
    just the surviving values.
    """
    cells: list[DCFSensitivityCell] = []
    for dr in _DISCOUNT_RATE_DELTAS:
        for dg in _TERMINAL_GROWTH_DELTAS:
            r_p = r + dr
            g_p = g + dg
            if g_p >= r_p:
                cells.append(
                    DCFSensitivityCell(
                        discount_rate=r_p,
                        terminal_growth=g_p,
                        enterprise_value=None,
                        skipped_reason=_GORDON_SKIP_REASON,
                    )
                )
                continue
            cells.append(
                DCFSensitivityCell(
                    discount_rate=r_p,
                    terminal_growth=g_p,
                    enterprise_value=_compute_ev(projections, r_p, g_p, tax),
                    skipped_reason=None,
                )
            )
    return cells


class DCFMethod(ValuationMethod):
    """Discounted Cash Flow valuation.

    Applicability requires at least 2 projection years, both rates set, and
    `terminal_growth_rate < discount_rate` (Gordon-model stability).

    Confidence: `min(1, n_years / 5) × completeness_ratio`, where completeness counts
    non-zero values across `revenue`, `ebitda`, `capex` for each projection year. (We
    treat `change_in_nwc == 0` as populated by default since it has a default of 0.)
    """

    name: ClassVar[str] = "dcf"
    description: ClassVar[str] = (
        "Discounted cash flow on the supplied projections, plus a Gordon-growth "
        "terminal value discounted back to the as-of date."
    )
    required_inputs: ClassVar[tuple[str, ...]] = (
        "projections",
        "discount_rate",
        "terminal_growth_rate",
    )

    @classmethod
    def describe(cls) -> MethodDescriptor:
        return MethodDescriptor(
            name=cls.name,
            description=cls.description,
            required_inputs=list(cls.required_inputs),
        )

    def is_applicable(self, request: ValuationRequest) -> bool:
        if request.projections is None or len(request.projections) < 2:
            return False
        if request.discount_rate is None or request.terminal_growth_rate is None:
            return False
        # Gordon stability — also avoids division by zero/negative on (r - g).
        return request.terminal_growth_rate < request.discount_rate

    def inapplicability_reason(self, request: ValuationRequest) -> str:
        if request.projections is None or len(request.projections) < 2:
            return "DCF requires at least 2 years of financial projections."
        if request.discount_rate is None:
            return "Discount rate is missing — DCF needs an auditor-supplied discount rate."
        if request.terminal_growth_rate is None:
            return (
                "Terminal growth rate is missing — DCF needs an auditor-supplied "
                "terminal growth rate."
            )
        if request.terminal_growth_rate >= request.discount_rate:
            return (
                "Gordon-growth instability: terminal growth rate must be strictly "
                "less than the discount rate."
            )
        return super().inapplicability_reason(request)

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

        cells = _run_sensitivity_grid(projections, r, g, tax)
        evs = [c.enterprise_value for c in cells if c.enterprise_value is not None]
        skipped = sum(1 for c in cells if c.enterprise_value is None)

        if not evs:
            # Defensive fallback: every grid cell hit Gordon instability. is_applicable
            # already enforces g < r at center, so this only fires for adversarial
            # inputs that bypass the gate. We still emit the (all-skipped) grid for
            # traceability so reviewers can see *why* every cell was rejected.
            center = _compute_ev(projections, r, g, tax)
            point = low = high = center
            grid_assumption = Assumption(
                name="Sensitivity grid",
                value="3x3 (discount_rate +/- 1pp x terminal_growth +/- 0.5pp)",
                rationale=(
                    "fallback: full grid skipped (every cell hit Gordon stability), "
                    "used center cell only."
                ),
            )
        else:
            low = min(evs)
            high = max(evs)
            point = (low + high) / Decimal(2)
            valid_cells = 9 - skipped
            grid_assumption = Assumption(
                name="Sensitivity grid",
                value="3x3 (discount_rate +/- 1pp x terminal_growth +/- 0.5pp)",
                rationale=(
                    f"Range = min/max across {valid_cells} valid cells; "
                    f"point = midpoint. {skipped} cell(s) skipped "
                    "(Gordon stability: g >= r)."
                ),
            )

        sensitivity_grid = DCFSensitivityGrid(
            center_discount_rate=r,
            center_terminal_growth=g,
            discount_rate_deltas=list(_DISCOUNT_RATE_DELTAS),
            terminal_growth_deltas=list(_TERMINAL_GROWTH_DELTAS),
            cells=cells,
            skipped_count=skipped,
        )

        # Confidence — horizon coverage × completeness.
        years_factor = min(Decimal(1), Decimal(n_years) / _CONFIDENCE_SATURATION_YEARS)
        completeness = self._completeness_ratio(projections)
        confidence = years_factor * completeness

        assumptions = self._build_assumptions(request, n_years, grid_assumption)
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

        valid_cells_for_notes = len(evs) if evs else 1
        return MethodResult(
            method_name=self.name,
            point_estimate=point,
            low=low,
            high=high,
            confidence=confidence,
            assumptions=assumptions,
            citations=citations,
            notes=(
                f"3x3 sensitivity grid (discount_rate +/- 1pp x terminal_growth "
                f"+/- 0.5pp) over {n_years} projection years; range = min/max "
                f"across {valid_cells_for_notes} valid cells, point = midpoint."
            ),
            dcf_sensitivity=sensitivity_grid,
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
    def _build_assumptions(
        request: ValuationRequest,
        n_years: int,
        grid_assumption: Assumption,
    ) -> list[Assumption]:
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
                value=_format_rate(request.discount_rate),
                rationale="Auditor-supplied WACC proxy.",
            ),
            Assumption(
                name="Terminal growth rate",
                value=_format_rate(request.terminal_growth_rate),
                rationale="Long-run nominal growth; must be < discount rate (Gordon stability).",
            ),
            Assumption(
                name="Tax rate",
                value=_format_rate(request.tax_rate),
                rationale=tax_rationale,
            ),
            Assumption(
                name="FCF formula",
                value="EBITDA × (1 − tax) − capex − ΔNWC",
                rationale="No D&A tax shield modeled — slightly conservative.",
            ),
            grid_assumption,
            Assumption(
                name="Confidence formula",
                value=f"min(1, {n_years}/5) × completeness_ratio",
                rationale=(
                    "Saturates at 5 projection years; completeness counts non-zero "
                    "revenue/ebitda/capex across years (ΔNWC excluded — default is 0)."
                ),
            ),
        ]
