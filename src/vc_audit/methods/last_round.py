"""Last-round market-adjusted valuation method.

Marks the most recent priced round to the public market by applying the reference
index's return between the round date and the as-of date. Confidence decays linearly
to zero over two years; the range is a flat ±15% to capture basis risk between any
single index and the company's specific industry beta.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import ClassVar

from vc_audit.data.index_provider import MarketIndexProvider
from vc_audit.methods.base import ValuationMethod
from vc_audit.methods.descriptor import MethodDescriptor
from vc_audit.models import (
    Assumption,
    Citation,
    MethodResult,
    ValuationRequest,
)

# Constants for the range haircut and age-decay window. Pulled to module-scope so the
# tests and the emitted Assumption strings agree without drift.
_RANGE_LOW_FACTOR = Decimal("0.85")
_RANGE_HIGH_FACTOR = Decimal("1.15")
_AGE_DECAY_DAYS = Decimal("730")


class LastRoundMethod(ValuationMethod):
    """Mark-to-market valuation anchored on the last priced round."""

    name: ClassVar[str] = "last_round"
    description: ClassVar[str] = (
        "Marks the last priced round to market using the reference index's return "
        "between the round date and the as-of date; confidence decays over two years."
    )
    required_inputs: ClassVar[tuple[str, ...]] = (
        "last_post_money_valuation",
        "last_round_date",
        "reference_index",
    )

    @classmethod
    def describe(cls) -> MethodDescriptor:
        return MethodDescriptor(
            name=cls.name,
            description=cls.description,
            required_inputs=list(cls.required_inputs),
        )

    def __init__(self, index_provider: MarketIndexProvider) -> None:
        self._index_provider = index_provider

    # ---------- applicability ----------

    def is_applicable(self, request: ValuationRequest) -> bool:
        """Method applies iff both round inputs are present AND the index can price both dates.

        Deferring the index-coverage check to `value()` would let `is_applicable` return
        True for inputs the method then can't actually price. Keeping it honest here means
        the Triangulator can trust an applicable method to run cleanly.
        """
        if request.last_post_money_valuation is None:
            return False
        if request.last_round_date is None:
            return False
        if not self._index_can_price(request.reference_index, request.last_round_date):
            return False
        return self._index_can_price(request.reference_index, request.as_of_date)

    def _index_can_price(self, index: str, on: date) -> bool:
        """Return True iff the underlying provider has a price on or before `on`."""
        try:
            self._index_provider.get_price(index, on)
        except KeyError:
            return False
        return True

    # ---------- valuation ----------

    def value(self, request: ValuationRequest) -> MethodResult:
        """Compute the index-adjusted valuation. Caller must have checked `is_applicable`."""
        # These narrow the Optional[...] fields. is_applicable guarantees they are set.
        assert request.last_post_money_valuation is not None
        assert request.last_round_date is not None

        last_post_money: Decimal = request.last_post_money_valuation
        round_date = request.last_round_date
        as_of = request.as_of_date
        index = request.reference_index

        price_then = self._index_provider.get_price(index, round_date)
        price_now = self._index_provider.get_price(index, as_of)

        index_return = price_now / price_then - Decimal(1)
        point = last_post_money * (Decimal(1) + index_return)
        low = point * _RANGE_LOW_FACTOR
        high = point * _RANGE_HIGH_FACTOR

        age_days = (as_of - round_date).days
        # max(0, 1 - age/730). Decimal-only arithmetic; clamp at zero.
        decay = Decimal(1) - Decimal(age_days) / _AGE_DECAY_DAYS
        confidence = decay if decay > 0 else Decimal(0)

        citation = Citation(
            source=f"MarketIndexProvider:{self._index_provider_source_id()}",
            description=(f"{index} {price_then} on {round_date} -> {price_now} on {as_of}"),
            retrieved_at=datetime.now(UTC),
            url=None,
        )

        assumptions = [
            Assumption(
                name="Reference index",
                value=index,
                rationale=(
                    "Used as a public-market proxy for the period return between last "
                    "round and as-of date."
                ),
            ),
            Assumption(
                name="Range factor",
                value="+/-15%",
                rationale=(
                    "Basis-risk haircut/expansion to reflect that the chosen index is "
                    "an imperfect proxy for the company's specific industry beta."
                ),
            ),
            Assumption(
                name="Index lookup strategy",
                value="nearest-prior date",
                rationale=(
                    "Returns the closing level of the most recent entry on or before "
                    "the requested date. Defensible heuristic in the absence of daily "
                    "granularity; emit as a known approximation rather than interpolating."
                ),
            ),
            Assumption(
                name="Age decay",
                value=f"{age_days} days; confidence = max(0, 1 - age/730)",
                rationale=(
                    "Last-round signal degrades as the round becomes stale; zero "
                    "confidence at 2 years."
                ),
            ),
        ]

        return MethodResult(
            method_name=self.name,
            point_estimate=point,
            low=low,
            high=high,
            confidence=confidence,
            assumptions=assumptions,
            citations=[citation],
        )

    def _index_provider_source_id(self) -> str:
        """Best-effort source-id extraction for citations.

        Concrete providers (e.g., `MockMarketIndexProvider`) expose `source_id`. The
        `MarketIndexProvider` Protocol does not require it — we degrade gracefully so
        a minimal fake (test double) without `source_id` still produces a valid citation.
        """
        return getattr(self._index_provider, "source_id", "unknown")
