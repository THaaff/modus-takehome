"""Inputs to a valuation run."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from vc_audit.models.company import PortfolioCompany
from vc_audit.models.types import DecimalStr


class FinancialProjection(BaseModel):
    """One forecast year of operating data, used by the DCF method."""

    model_config = ConfigDict(frozen=True)

    year: int = Field(ge=1, description="Forecast year offset from valuation date (1, 2, 3, ...).")
    revenue: DecimalStr
    ebitda: DecimalStr
    capex: DecimalStr
    change_in_nwc: DecimalStr = Decimal(0)


class ValuationRequest(BaseModel):
    """Single-company valuation request. Each method picks the inputs it needs."""

    company: PortfolioCompany

    # Comps inputs
    revenue: DecimalStr | None = None
    ebitda: DecimalStr | None = None

    # Last Round inputs
    last_post_money_valuation: DecimalStr | None = None
    last_round_date: date | None = None
    reference_index: str = "NASDAQ"

    # DCF inputs
    projections: list[FinancialProjection] | None = None
    discount_rate: DecimalStr | None = Field(default=None, gt=0, lt=1)
    terminal_growth_rate: DecimalStr | None = Field(default=None, gt=0, lt=1)
    tax_rate: DecimalStr = Field(
        default=Decimal("0.21"),
        ge=0,
        lt=1,
        description="Effective tax rate. Default 0.21 (US corporate).",
    )

    # Auditor controls
    method_weights: dict[str, DecimalStr] | None = Field(
        default=None,
        description="Optional per-method weight override. Must sum > 0; will be normalized.",
    )
    as_of_date: date = Field(default_factory=date.today)
