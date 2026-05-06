"""Outputs of a valuation run."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from vc_audit.models.assumption import Assumption
from vc_audit.models.citation import Citation
from vc_audit.models.company import PortfolioCompany
from vc_audit.models.request import ValuationRequest
from vc_audit.models.types import DecimalStr


class MethodResult(BaseModel):
    """Output of a single valuation method."""

    method_name: str
    point_estimate: DecimalStr
    low: DecimalStr
    high: DecimalStr
    confidence: DecimalStr = Field(
        ge=0,
        le=1,
        description="Raw confidence in [0, 1]; the Triangulator normalizes to weights.",
    )
    assumptions: list[Assumption] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    notes: str | None = None


class MethodWeight(BaseModel):
    """How much one method contributed to the final point estimate."""

    method_name: str
    raw_confidence: DecimalStr = Field(ge=0, le=1)
    normalized_weight: DecimalStr = Field(
        ge=0, le=1, description="Sums to 1 across all methods used in this run."
    )
    overridden: bool = False


class TriangulatedValuation(BaseModel):
    """Headline output: the audit artifact."""

    company: PortfolioCompany
    as_of_date: date
    point_estimate: DecimalStr
    range_low: DecimalStr
    range_high: DecimalStr
    dispersion: DecimalStr = Field(
        ge=0,
        description="(range_high - range_low) / point_estimate. Flag-worthy when > 0.5.",
    )
    dispersion_flag: bool
    method_results: list[MethodResult]
    weights: list[MethodWeight]
    request: ValuationRequest  # echoed for full audit trail
    generated_at: datetime

    @classmethod
    def dispersion_threshold(cls) -> Decimal:
        """Threshold above which `dispersion_flag` should be True. See discussion.md §5c."""
        return Decimal("0.5")
