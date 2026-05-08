"""Tests for CompsMethod: applicability, numeric correctness, confidence, assumptions.

Inline helpers only — no shared conftest fixtures, so other test modules can add their
own conftest later without inheriting irrelevant comps wiring.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from vc_audit.data.comps_provider import Comp, CompsProvider, MockCompsProvider
from vc_audit.methods.comps import CompsMethod
from vc_audit.models import (
    Assumption,
    PortfolioCompany,
    ValuationRequest,
)

# --------------------------------------------------------------------- helpers


class _StaticProvider:
    """Tiny in-memory CompsProvider for deterministic numeric tests."""

    source_id: str = "static_test"

    def __init__(self, comps: list[Comp]) -> None:
        self._comps = comps

    def get_comps(self, sector: str) -> list[Comp]:
        return [c for c in self._comps if c.sector == sector]


def _make_request(
    sector: str | None = "SaaS",
    revenue: Decimal | None = Decimal("100"),
    ebitda: Decimal | None = None,
    name: str = "Acme",
) -> ValuationRequest:
    return ValuationRequest(
        company=PortfolioCompany(name=name, sector=sector),
        revenue=revenue,
        ebitda=ebitda,
    )


def _make_comp(
    ticker: str,
    sector: str,
    revenue: Decimal,
    enterprise_value: Decimal,
    ebitda: Decimal | None = None,
) -> Comp:
    return Comp(
        ticker=ticker,
        sector=sector,
        revenue=revenue,
        enterprise_value=enterprise_value,
        ebitda=ebitda,
    )


# --------------------------------------------------------------------- applicability


def test_applicability_missing_sector_is_false() -> None:
    provider = _StaticProvider([_make_comp("A", "SaaS", Decimal("10"), Decimal("80"))])
    method = CompsMethod(provider)
    request = _make_request(sector=None, revenue=Decimal("100"))
    assert method.is_applicable(request) is False


def test_applicability_missing_revenue_is_false() -> None:
    provider = _StaticProvider([_make_comp("A", "SaaS", Decimal("10"), Decimal("80"))])
    method = CompsMethod(provider)
    request = _make_request(sector="SaaS", revenue=None)
    assert method.is_applicable(request) is False


def test_applicability_zero_peers_is_false() -> None:
    provider = _StaticProvider([])  # nothing in any sector
    method = CompsMethod(provider)
    request = _make_request(sector="SaaS", revenue=Decimal("100"))
    assert method.is_applicable(request) is False


def test_applicability_one_peer_is_true() -> None:
    provider = _StaticProvider([_make_comp("A", "SaaS", Decimal("10"), Decimal("80"))])
    method = CompsMethod(provider)
    request = _make_request(sector="SaaS", revenue=Decimal("100"))
    assert method.is_applicable(request) is True


def test_provider_satisfies_protocol_structurally() -> None:
    """CompsProvider is runtime_checkable; both static and mock providers should match."""
    static = _StaticProvider([])
    mock = MockCompsProvider()
    assert isinstance(static, CompsProvider)
    assert isinstance(mock, CompsProvider)


# --------------------------------------------------------------------- numeric correctness


def test_numeric_correctness_three_known_multiples() -> None:
    """Three peers with EV/Rev multiples of 4x, 8x, 16x → median=8, p25=6, p75=12.

    Target revenue = 100 → point=800, low=600, high=1200.
    Linear interpolation: p25 idx 0.5 → 4 + 0.5*(8-4) = 6;
                         p75 idx 1.5 → 8 + 0.5*(16-8) = 12.
    """
    comps = [
        _make_comp("LO", "SaaS", revenue=Decimal("10"), enterprise_value=Decimal("40")),
        _make_comp("MD", "SaaS", revenue=Decimal("10"), enterprise_value=Decimal("80")),
        _make_comp("HI", "SaaS", revenue=Decimal("10"), enterprise_value=Decimal("160")),
    ]
    provider = _StaticProvider(comps)
    method = CompsMethod(provider)
    request = _make_request(sector="SaaS", revenue=Decimal("100"))

    result = method.value(request)
    assert result.point_estimate == Decimal("800")
    assert result.low == Decimal("600")
    assert result.high == Decimal("1200")


def test_numeric_correctness_combines_revenue_and_ebitda_metrics() -> None:
    """Both metrics produce estimates → arithmetic mean element-wise.

    Three peers, all with EV/Rev = {4, 8, 16} and EV/EBITDA = {10, 20, 40}.
    Target: revenue=100, ebitda=50.
    Revenue side:  (median 8 * 100, p25 6 * 100, p75 12 * 100) = (800, 600, 1200)
    EBITDA  side:  (median 20 * 50, p25 15 * 50, p75 30 * 50) = (1000, 750, 1500)
    Mean:          (900, 675, 1350).
    """
    comps = [
        _make_comp(
            "LO",
            "SaaS",
            revenue=Decimal("10"),
            enterprise_value=Decimal("40"),
            ebitda=Decimal("4"),
        ),
        _make_comp(
            "MD",
            "SaaS",
            revenue=Decimal("10"),
            enterprise_value=Decimal("80"),
            ebitda=Decimal("4"),
        ),
        _make_comp(
            "HI",
            "SaaS",
            revenue=Decimal("10"),
            enterprise_value=Decimal("160"),
            ebitda=Decimal("4"),
        ),
    ]
    provider = _StaticProvider(comps)
    method = CompsMethod(provider)
    request = _make_request(sector="SaaS", revenue=Decimal("100"), ebitda=Decimal("50"))

    result = method.value(request)
    assert result.point_estimate == Decimal("900")
    assert result.low == Decimal("675")
    assert result.high == Decimal("1350")


def test_low_le_point_le_high_invariant() -> None:
    comps = [
        _make_comp("LO", "SaaS", revenue=Decimal("10"), enterprise_value=Decimal("40")),
        _make_comp("MD", "SaaS", revenue=Decimal("10"), enterprise_value=Decimal("80")),
        _make_comp("HI", "SaaS", revenue=Decimal("10"), enterprise_value=Decimal("160")),
    ]
    provider = _StaticProvider(comps)
    method = CompsMethod(provider)
    result = method.value(_make_request(sector="SaaS", revenue=Decimal("100")))
    assert result.low <= result.point_estimate <= result.high


# --------------------------------------------------------------------- confidence scaling


@pytest.mark.parametrize(
    "n_peers, expected",
    [
        (1, Decimal(1) / Decimal(8)),
        (2, Decimal(2) / Decimal(8)),
        (4, Decimal(4) / Decimal(8)),
        (8, Decimal(1)),
        (16, Decimal(1)),  # clamped at 1.0
    ],
)
def test_confidence_scales_with_peer_count(n_peers: int, expected: Decimal) -> None:
    """Confidence is min(1, n/8) regardless of peer-multiple distribution."""
    comps = [
        _make_comp(f"P{i}", "SaaS", revenue=Decimal("10"), enterprise_value=Decimal("80"))
        for i in range(n_peers)
    ]
    provider = _StaticProvider(comps)
    method = CompsMethod(provider)
    result = method.value(_make_request(sector="SaaS", revenue=Decimal("100")))
    assert result.confidence == expected


# --------------------------------------------------------------------- citations


def test_citation_populated_with_provider_source() -> None:
    comps = [_make_comp("AAA", "SaaS", Decimal("10"), Decimal("80"))]
    provider = _StaticProvider(comps)
    method = CompsMethod(provider)
    result = method.value(_make_request(sector="SaaS", revenue=Decimal("100")))
    assert len(result.citations) >= 1
    citation = result.citations[0]
    assert citation.source == "CompsProvider:static_test"
    assert "AAA" in citation.description
    assert "sector=SaaS" in citation.description
    assert "n=1" in citation.description


# --------------------------------------------------------------------- sparse-peer assumption


def _has_assumption(assumptions: list[Assumption], name: str) -> bool:
    return any(a.name == name for a in assumptions)


@pytest.mark.parametrize("n_peers", [1, 2])
def test_sparse_peer_assumption_present_below_threshold(n_peers: int) -> None:
    comps = [
        _make_comp(f"P{i}", "SaaS", revenue=Decimal("10"), enterprise_value=Decimal("80"))
        for i in range(n_peers)
    ]
    provider = _StaticProvider(comps)
    method = CompsMethod(provider)
    result = method.value(_make_request(sector="SaaS", revenue=Decimal("100")))
    assert _has_assumption(result.assumptions, "Sparse peer set"), (
        f"Expected 'Sparse peer set' assumption with {n_peers} peer(s)"
    )


@pytest.mark.parametrize("n_peers", [3, 5, 8, 12])
def test_sparse_peer_assumption_absent_at_or_above_threshold(n_peers: int) -> None:
    comps = [
        _make_comp(f"P{i}", "SaaS", revenue=Decimal("10"), enterprise_value=Decimal("80"))
        for i in range(n_peers)
    ]
    provider = _StaticProvider(comps)
    method = CompsMethod(provider)
    result = method.value(_make_request(sector="SaaS", revenue=Decimal("100")))
    assert not _has_assumption(result.assumptions, "Sparse peer set"), (
        f"Did not expect 'Sparse peer set' assumption with {n_peers} peer(s)"
    )


# --------------------------------------------------------------------- end-to-end with real fixture


def test_end_to_end_with_real_mock_provider_saas() -> None:
    """Real `MockCompsProvider` against the SaaS slice of `comp_universe.json`.

    Asserts only structural well-formedness: positive point, low <= point <= high,
    confidence in [0, 1], at least one citation. Specific multiples will shift if
    the fixture changes — we don't pin them.
    """
    provider = MockCompsProvider()
    method = CompsMethod(provider)
    request = ValuationRequest(
        company=PortfolioCompany(name="TargetCo", sector="SaaS"),
        revenue=Decimal("500"),
        ebitda=Decimal("80"),
    )

    assert method.is_applicable(request)
    result = method.value(request)
    assert result.method_name == "comps"
    assert result.point_estimate > Decimal(0)
    assert result.low <= result.point_estimate <= result.high
    assert Decimal(0) <= result.confidence <= Decimal(1)
    assert len(result.citations) >= 1
    assert result.citations[0].source == "CompsProvider:mock_universe_v1"


def test_mock_provider_default_path_resolves() -> None:
    """Default fixture path is bundled with the package and parses cleanly."""
    provider = MockCompsProvider()
    assert provider.source_id == "mock_universe_v1"
    saas = provider.get_comps("SaaS")
    assert len(saas) >= 4  # fixture guarantees >=4 per sector


def test_mock_provider_unknown_sector_returns_empty() -> None:
    provider = MockCompsProvider()
    assert provider.get_comps("NonexistentSector") == []


def test_mock_provider_explicit_path(tmp_path: Path) -> None:
    """Pass an explicit fixture path; loader honors it."""
    fixture = tmp_path / "tiny.json"
    fixture.write_text(
        '{"as_of": "2025-01-01", "source_id": "tiny", '
        '"comps": [{"ticker":"X","sector":"S","revenue":"1","ebitda":null,'
        '"enterprise_value":"10"}]}',
        encoding="utf-8",
    )
    provider = MockCompsProvider(fixture_path=fixture)
    assert provider.source_id == "tiny"
    assert len(provider.get_comps("S")) == 1
    assert provider.get_comps("S")[0].ticker == "X"
