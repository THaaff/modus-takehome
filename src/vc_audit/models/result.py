"""Outputs of a valuation run.

Money fields are expressed in $M (millions of US dollars) and serialized to 2dp.
Fractions (confidence, weights, dispersion) are unitless in [0, 1] (or ≥0 for
dispersion as a ratio) and serialized to 4dp. Internal math stays full-precision.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from vc_audit.models.assumption import Assumption
from vc_audit.models.citation import Citation
from vc_audit.models.company import PortfolioCompany
from vc_audit.models.request import ValuationRequest
from vc_audit.models.types import DecimalStr, Fraction4dp, Money2dp


class DCFSensitivityCell(BaseModel):
    """One cell of the DCF 3x3 sensitivity grid.

    `enterprise_value` is None when the cell was skipped (Gordon instability:
    perturbed terminal growth >= perturbed discount rate). `skipped_reason` carries
    a human-readable explanation in that case.
    """

    discount_rate: DecimalStr = Field(description="Perturbed discount rate (e.g. 0.13).")
    terminal_growth: DecimalStr = Field(description="Perturbed terminal growth rate.")
    enterprise_value: Money2dp | None = Field(
        default=None,
        description="Cell EV in $M, or None when the cell was skipped.",
    )
    skipped_reason: str | None = Field(
        default=None,
        description="Reason this cell was skipped (e.g., Gordon stability violation).",
    )


class DCFSensitivityGrid(BaseModel):
    """The full 3x3 grid produced by DCFMethod, preserved for audit traceability.

    Lets reviewers see the *shape* of the sensitivity (where EV blows up or
    compresses), not just the bounding low/high. Cells are emitted in row-major
    order: outer loop over discount-rate deltas, inner over terminal-growth deltas.
    """

    center_discount_rate: DecimalStr = Field(
        description="The auditor-supplied discount rate (grid center)."
    )
    center_terminal_growth: DecimalStr = Field(
        description="The auditor-supplied terminal growth rate (grid center)."
    )
    discount_rate_deltas: list[DecimalStr] = Field(
        description="Offsets applied to the center discount rate (length 3)."
    )
    terminal_growth_deltas: list[DecimalStr] = Field(
        description="Offsets applied to the center terminal growth (length 3)."
    )
    cells: list[DCFSensitivityCell] = Field(
        description="All 9 cells in row-major order (discount_rate outer, growth inner)."
    )
    skipped_count: int = Field(
        ge=0,
        le=9,
        description="Number of cells skipped due to Gordon stability violations.",
    )


class MethodResult(BaseModel):
    """Output of a single valuation method."""

    method_name: str
    point_estimate: Money2dp = Field(description="Point estimate in $M.")
    low: Money2dp = Field(description="Range lower bound in $M.")
    high: Money2dp = Field(description="Range upper bound in $M.")
    confidence: Fraction4dp = Field(
        ge=0,
        le=1,
        description=(
            "Raw confidence in [0, 1] (unitless). 0 = no signal, 1 = full signal. "
            "The Triangulator normalizes across methods to produce weights."
        ),
    )
    assumptions: list[Assumption] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    notes: str | None = None
    dcf_sensitivity: DCFSensitivityGrid | None = Field(
        default=None,
        description=(
            "DCF-only: the full 3x3 sensitivity grid. None for non-DCF methods. "
            "Method-specific so reviewers can audit the EV shape across the perturbed grid."
        ),
    )


class SkippedMethod(BaseModel):
    """A registered method that was *not* run for this request, plus the reason.

    Surfaced so auditors can see at a glance why the triangulated estimate is
    leaning on a subset of methods — e.g., DCF skipped because no projections
    were provided. The reason string is intended for humans, not machine parsing.
    """

    method_name: str
    reason: str


class MethodWeight(BaseModel):
    """How much one method contributed to the final point estimate."""

    method_name: str
    raw_confidence: Fraction4dp = Field(
        ge=0, le=1, description="The method's own confidence in [0, 1] (unitless)."
    )
    normalized_weight: Fraction4dp = Field(
        ge=0,
        le=1,
        description=(
            "Share of the final point estimate this method contributed (unitless). "
            "Sums to 1 across all methods used in this run."
        ),
    )
    overridden: bool = Field(
        default=False,
        description="True if the auditor supplied this weight via request.method_weights.",
    )


class TriangulatedValuation(BaseModel):
    """Headline output: the audit artifact."""

    company: PortfolioCompany
    as_of_date: date
    point_estimate: Money2dp = Field(description="Triangulated point estimate in $M.")
    range_low: Money2dp = Field(
        description="Min low across applicable methods, in $M (not weighted)."
    )
    range_high: Money2dp = Field(
        description="Max high across applicable methods, in $M (not weighted)."
    )
    dispersion: Fraction4dp = Field(
        ge=0,
        description=(
            "(range_high - range_low) / point_estimate as a unitless ratio. "
            "Flag-worthy when > 0.5 (i.e., the high-low spread exceeds half the point)."
        ),
    )
    dispersion_flag: bool
    outlier_method_names: list[str] = Field(
        default_factory=list,
        description=(
            "Method names whose point estimate is >2× or <0.5× the median across "
            "applicable methods. Empty if fewer than 3 methods or no outliers."
        ),
    )
    method_results: list[MethodResult]
    skipped_methods: list[SkippedMethod] = Field(
        default_factory=list,
        description=(
            "Registered methods that were not applicable to this request. Each entry "
            "names the method and the human-readable reason (e.g., missing inputs)."
        ),
    )
    weights: list[MethodWeight]
    request: ValuationRequest  # echoed for full audit trail
    generated_at: datetime

    @classmethod
    def dispersion_threshold(cls) -> Decimal:
        """Threshold above which `dispersion_flag` should be True."""
        return Decimal("0.5")
