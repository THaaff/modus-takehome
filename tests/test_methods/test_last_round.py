"""Tests for `LastRoundMethod`.

Covers applicability, the index-return calc, the +/-15% range, age-based confidence
decay, citations, out-of-range graceful behavior, and one end-to-end run against the
real `MockMarketIndexProvider` and shipped fixture.

Test doubles are inlined per project convention (no `tests/conftest.py`).
"""

from datetime import date
from decimal import Decimal

from vc_audit.data import MarketIndexProvider, MockMarketIndexProvider
from vc_audit.methods import LastRoundMethod
from vc_audit.models import PortfolioCompany, ValuationRequest

# ---------- Test doubles ----------


class _FakeIndex:
    """Minimal `MarketIndexProvider` returning fixed `then` and `now` prices.

    The class assumes the two requested dates are distinct (one earlier, one later).
    Hits to `then_date` (and earlier) return `then_price`; hits to `now_date` return
    `now_price`. Anything else triggers a deliberate `KeyError` so tests fail loudly
    if a method asks for an unexpected date.
    """

    source_id = "fake_index_v1"

    def __init__(
        self,
        then_date: date,
        then_price: Decimal,
        now_date: date,
        now_price: Decimal,
    ) -> None:
        self._then_date = then_date
        self._then_price = then_price
        self._now_date = now_date
        self._now_price = now_price

    def get_price(self, index: str, on: date) -> Decimal:
        if on == self._then_date:
            return self._then_price
        if on == self._now_date:
            return self._now_price
        raise KeyError(f"unexpected lookup for {index} on {on}")


class _AlwaysKeyError:
    """A provider that pretends to know nothing — used to test out-of-range applicability."""

    source_id = "empty"

    def get_price(self, index: str, on: date) -> Decimal:
        raise KeyError(f"no data for {index} on {on}")


def _request(
    *,
    last_post_money: Decimal | None = Decimal("100000000"),
    last_round_date: date | None = date(2024, 6, 1),
    as_of_date: date = date(2025, 6, 1),
    reference_index: str = "NASDAQ",
) -> ValuationRequest:
    return ValuationRequest(
        company=PortfolioCompany(name="Acme", sector="SaaS"),
        last_post_money_valuation=last_post_money,
        last_round_date=last_round_date,
        as_of_date=as_of_date,
        reference_index=reference_index,
    )


# ---------- Applicability ----------


def test_not_applicable_without_last_post_money() -> None:
    method = LastRoundMethod(
        _FakeIndex(date(2024, 6, 1), Decimal("10000"), date(2025, 6, 1), Decimal("12000"))
    )
    request = _request(last_post_money=None)
    assert method.is_applicable(request) is False


def test_not_applicable_without_last_round_date() -> None:
    method = LastRoundMethod(
        _FakeIndex(date(2024, 6, 1), Decimal("10000"), date(2025, 6, 1), Decimal("12000"))
    )
    request = _request(last_round_date=None)
    assert method.is_applicable(request) is False


def test_applicable_when_inputs_present_and_index_in_range() -> None:
    method = LastRoundMethod(
        _FakeIndex(date(2024, 6, 1), Decimal("10000"), date(2025, 6, 1), Decimal("12000"))
    )
    assert method.is_applicable(_request()) is True


def test_not_applicable_when_index_lacks_data() -> None:
    """If the provider raises KeyError for a date, the method should report False, not crash."""
    method = LastRoundMethod(_AlwaysKeyError())
    assert method.is_applicable(_request()) is False


# ---------- Return calc ----------


def test_point_estimate_uses_index_return() -> None:
    """price_now/price_then = 1.20 -> point = 100M * 1.20 = 120M."""
    method = LastRoundMethod(
        _FakeIndex(date(2024, 6, 1), Decimal("10000"), date(2025, 6, 1), Decimal("12000"))
    )
    result = method.value(_request())
    assert result.point_estimate == Decimal("120000000")


def test_negative_index_return_pulls_point_below_post_money() -> None:
    method = LastRoundMethod(
        _FakeIndex(date(2024, 6, 1), Decimal("12000"), date(2025, 6, 1), Decimal("9000"))
    )
    result = method.value(_request())
    # 9000/12000 - 1 = -0.25; 100M * 0.75 = 75M
    assert result.point_estimate == Decimal("75000000")


# ---------- Range factor ----------


def test_range_is_85_to_115_percent_of_point() -> None:
    method = LastRoundMethod(
        _FakeIndex(date(2024, 6, 1), Decimal("10000"), date(2025, 6, 1), Decimal("12000"))
    )
    result = method.value(_request())
    assert result.low == result.point_estimate * Decimal("0.85")
    assert result.high == result.point_estimate * Decimal("1.15")


# ---------- Age-based confidence decay ----------


def test_confidence_full_when_round_is_fresh() -> None:
    """0 days old -> confidence == 1.0."""
    same_day = date(2025, 6, 1)
    method = LastRoundMethod(_FakeIndex(same_day, Decimal("10000"), same_day, Decimal("10000")))
    result = method.value(_request(last_round_date=same_day, as_of_date=same_day))
    assert result.confidence == Decimal(1)


def test_confidence_half_at_one_year() -> None:
    """365 / 730 = 0.5 exactly."""
    round_date = date(2024, 6, 1)
    as_of = date(2025, 6, 1)  # 365 days later
    method = LastRoundMethod(_FakeIndex(round_date, Decimal("10000"), as_of, Decimal("10000")))
    result = method.value(_request(last_round_date=round_date, as_of_date=as_of))
    # 1 - 365/730 = 0.5
    assert result.confidence == Decimal("0.5")


def test_confidence_zero_at_two_years() -> None:
    round_date = date(2023, 6, 1)
    as_of = date(2025, 5, 31)  # exactly 730 days
    method = LastRoundMethod(_FakeIndex(round_date, Decimal("10000"), as_of, Decimal("10000")))
    result = method.value(_request(last_round_date=round_date, as_of_date=as_of))
    assert (as_of - round_date).days == 730
    assert result.confidence == Decimal(0)


def test_confidence_clamped_to_zero_past_two_years() -> None:
    round_date = date(2023, 1, 1)
    as_of = date(2025, 3, 12)  # > 730 days
    method = LastRoundMethod(_FakeIndex(round_date, Decimal("10000"), as_of, Decimal("10000")))
    result = method.value(_request(last_round_date=round_date, as_of_date=as_of))
    assert (as_of - round_date).days > 730
    assert result.confidence == Decimal(0)


# ---------- Citations ----------


def test_citation_uses_provider_source_id() -> None:
    method = LastRoundMethod(
        _FakeIndex(date(2024, 6, 1), Decimal("10000"), date(2025, 6, 1), Decimal("12000"))
    )
    result = method.value(_request())
    assert len(result.citations) == 1
    citation = result.citations[0]
    assert citation.source == "MarketIndexProvider:fake_index_v1"
    # description should reference both prices and both dates
    assert "10000" in citation.description
    assert "12000" in citation.description
    assert "2024-06-01" in citation.description
    assert "2025-06-01" in citation.description


def test_citation_retrieved_at_is_timezone_aware() -> None:
    method = LastRoundMethod(
        _FakeIndex(date(2024, 6, 1), Decimal("10000"), date(2025, 6, 1), Decimal("12000"))
    )
    result = method.value(_request())
    assert result.citations[0].retrieved_at.tzinfo is not None


# ---------- Assumptions ----------


def test_assumptions_cover_required_axes() -> None:
    """Each axis (index, range, lookup, age) should be present by name."""
    method = LastRoundMethod(
        _FakeIndex(date(2024, 6, 1), Decimal("10000"), date(2025, 6, 1), Decimal("12000"))
    )
    result = method.value(_request())
    names = {a.name for a in result.assumptions}
    assert names == {"Reference index", "Range factor", "Index lookup strategy", "Age decay"}


# ---------- Out-of-range against real MockMarketIndexProvider ----------


def test_real_provider_out_of_range_is_not_applicable() -> None:
    """A round date before the earliest fixture entry: is_applicable False, no exception."""
    provider = MockMarketIndexProvider()
    method = LastRoundMethod(provider)
    request = _request(
        last_round_date=date(2010, 1, 1),  # well before fixture starts (2021)
        as_of_date=date(2025, 6, 1),
    )
    assert method.is_applicable(request) is False


# ---------- End-to-end against the shipped fixture ----------


def test_end_to_end_against_real_fixture_is_well_formed() -> None:
    provider = MockMarketIndexProvider()
    method = LastRoundMethod(provider)
    request = _request(
        last_post_money=Decimal("100000000"),
        last_round_date=date(2023, 6, 30),
        as_of_date=date(2025, 6, 30),
    )
    assert method.is_applicable(request) is True
    result = method.value(request)
    assert result.method_name == "last_round"
    assert result.point_estimate > Decimal(0)
    assert result.low == result.point_estimate * Decimal("0.85")
    assert result.high == result.point_estimate * Decimal("1.15")
    assert Decimal(0) <= result.confidence <= Decimal(1)
    # 730 days between 2023-06-30 and 2025-06-29 -> 730 days exactly is 2025-06-29.
    # 2023-06-30 -> 2025-06-30 is 731 days, so confidence should clamp to zero.
    assert result.confidence == Decimal(0)
    assert len(result.citations) == 1
    assert result.citations[0].source == f"MarketIndexProvider:{provider.source_id}"


def test_real_provider_satisfies_protocol() -> None:
    """Sanity: MockMarketIndexProvider satisfies MarketIndexProvider structurally."""
    assert isinstance(MockMarketIndexProvider(), MarketIndexProvider)
