"""Sanity checks that the strategy ABC and the provider Protocols hold their shape."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from vc_audit.data import Comp, CompsProvider, MarketIndexProvider
from vc_audit.methods import NoApplicableMethodError, ValuationMethod
from vc_audit.models import (
    Assumption,
    Citation,
    MethodResult,
    PortfolioCompany,
    ValuationRequest,
)


def test_valuation_method_is_abstract() -> None:
    """Cannot instantiate ValuationMethod directly — proves it's truly abstract."""
    with pytest.raises(TypeError):
        ValuationMethod()  # type: ignore[abstract]


def test_concrete_subclass_constructs_and_runs() -> None:
    """A trivial subclass implementing both methods should construct and behave."""

    class _Always(ValuationMethod):
        name = "always"

        def is_applicable(self, request: ValuationRequest) -> bool:
            return True

        def value(self, request: ValuationRequest) -> MethodResult:
            return MethodResult(
                method_name=self.name,
                point_estimate=Decimal("1"),
                low=Decimal("1"),
                high=Decimal("1"),
                confidence=Decimal("0.5"),
                assumptions=[Assumption(name="n", value="v", rationale="r")],
                citations=[
                    Citation(
                        source="test",
                        description="d",
                        retrieved_at=datetime(2026, 5, 6, 12, 0, 0),
                    )
                ],
            )

    method = _Always()
    request = ValuationRequest(company=PortfolioCompany(name="Acme"))
    assert method.is_applicable(request)
    result = method.value(request)
    assert result.method_name == "always"
    assert result.point_estimate == Decimal("1")


def test_no_applicable_method_error_is_an_exception() -> None:
    assert issubclass(NoApplicableMethodError, Exception)


# ---------- Provider Protocols (structural) ----------


def test_comps_provider_structural_match() -> None:
    """An object with the right method shape should satisfy CompsProvider via runtime_checkable."""

    class _MockComps:
        def get_comps(self, sector: str) -> list[Comp]:
            return []

    assert isinstance(_MockComps(), CompsProvider)


def test_comps_provider_structural_mismatch() -> None:
    class _NotAComps:
        def something_else(self) -> None:
            return None

    assert not isinstance(_NotAComps(), CompsProvider)


def test_market_index_provider_structural_match() -> None:
    class _MockIndex:
        def get_price(self, index: str, on: date) -> Decimal:
            return Decimal("100")

    assert isinstance(_MockIndex(), MarketIndexProvider)
