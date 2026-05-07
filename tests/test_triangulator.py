"""Triangulator: weighting, dispersion, override validation, and applicability gating.

Tests use ad-hoc `ValuationMethod` subclasses (one per test case) to keep this stream
isolated from the real Comps/LastRound/DCF methods on other branches.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar

import pytest

from vc_audit.engine import Triangulator
from vc_audit.methods import NoApplicableMethodError, ValuationMethod
from vc_audit.models import (
    Citation,
    MethodResult,
    PortfolioCompany,
    ValuationRequest,
)

# ---------- Fake-method builder ----------
#
# Build a fresh ValuationMethod subclass per test so each instance has its own `name`
# ClassVar without resorting to per-instance assignment (which mypy --strict rejects).


def _fake_method_class(
    name_: str,
    *,
    applicable: bool,
    point: Decimal,
    low: Decimal,
    high: Decimal,
    confidence: Decimal,
) -> type[ValuationMethod]:
    class _Fake(ValuationMethod):
        name: ClassVar[str] = name_

        def is_applicable(self, request: ValuationRequest) -> bool:
            return applicable

        def inapplicability_reason(self, request: ValuationRequest) -> str:
            return f"fake reason for {name_}"

        def value(self, request: ValuationRequest) -> MethodResult:
            return MethodResult(
                method_name=self.name,
                point_estimate=point,
                low=low,
                high=high,
                confidence=confidence,
                citations=[
                    Citation(
                        source=f"fake:{self.name}",
                        description="test",
                        retrieved_at=datetime(2026, 5, 6, 12, 0, 0, tzinfo=UTC),
                    )
                ],
            )

    return _Fake


def _fake(
    name: str,
    *,
    applicable: bool = True,
    point: Decimal = Decimal("100"),
    low: Decimal = Decimal("80"),
    high: Decimal = Decimal("120"),
    confidence: Decimal = Decimal("0.5"),
) -> ValuationMethod:
    cls = _fake_method_class(
        name,
        applicable=applicable,
        point=point,
        low=low,
        high=high,
        confidence=confidence,
    )
    return cls()


def _request(
    method_weights: dict[str, Decimal] | None = None,
) -> ValuationRequest:
    return ValuationRequest(
        company=PortfolioCompany(name="Acme", sector="SaaS"),
        method_weights=method_weights,
    )


# ---------- Single applicable method ----------


def test_single_method_weight_is_one() -> None:
    method = _fake(
        "method_a",
        point=Decimal("100"),
        low=Decimal("80"),
        high=Decimal("120"),
        confidence=Decimal("0.6"),
    )
    valuation = Triangulator([method]).value(_request())
    assert valuation.point_estimate == Decimal("100")
    assert valuation.range_low == Decimal("80")
    assert valuation.range_high == Decimal("120")
    assert len(valuation.weights) == 1
    assert valuation.weights[0].normalized_weight == Decimal("1")
    assert valuation.weights[0].overridden is False
    # dispersion = (120 - 80) / 100 = 0.4
    assert valuation.dispersion == Decimal("0.4")
    assert valuation.dispersion_flag is False


# ---------- Multi-method weighted average ----------


def test_multi_method_confidence_weighted_average() -> None:
    """3 methods with known points and confidences; assert exact weighted avg."""
    methods = [
        _fake(
            "method_a",
            point=Decimal("100"),
            low=Decimal("80"),
            high=Decimal("120"),
            confidence=Decimal("0.5"),
        ),
        _fake(
            "method_b",
            point=Decimal("200"),
            low=Decimal("150"),
            high=Decimal("250"),
            confidence=Decimal("0.3"),
        ),
        _fake(
            "method_c",
            point=Decimal("300"),
            low=Decimal("250"),
            high=Decimal("350"),
            confidence=Decimal("0.2"),
        ),
    ]
    valuation = Triangulator(methods).value(_request())
    # weights: 0.5/1.0, 0.3/1.0, 0.2/1.0 = 0.5, 0.3, 0.2
    # point: 0.5*100 + 0.3*200 + 0.2*300 = 50 + 60 + 60 = 170
    assert valuation.point_estimate == Decimal("170")
    assert valuation.range_low == Decimal("80")
    assert valuation.range_high == Decimal("350")
    weights_by_name = {w.method_name: w.normalized_weight for w in valuation.weights}
    assert weights_by_name["method_a"] == Decimal("0.5")
    assert weights_by_name["method_b"] == Decimal("0.3")
    assert weights_by_name["method_c"] == Decimal("0.2")
    assert all(not w.overridden for w in valuation.weights)


# ---------- Manual override ----------


def test_manual_override_normalizes_and_marks_overridden() -> None:
    methods = [
        _fake(
            "method_a",
            point=Decimal("100"),
            low=Decimal("80"),
            high=Decimal("120"),
            confidence=Decimal("0.9"),
        ),
        _fake(
            "method_b",
            point=Decimal("200"),
            low=Decimal("150"),
            high=Decimal("250"),
            confidence=Decimal("0.1"),
        ),
    ]
    valuation = Triangulator(methods).value(
        _request(method_weights={"method_a": Decimal("0.5"), "method_b": Decimal("0.5")})
    )
    weights_by_name = {w.method_name: w for w in valuation.weights}
    assert weights_by_name["method_a"].normalized_weight == Decimal("0.5")
    assert weights_by_name["method_b"].normalized_weight == Decimal("0.5")
    assert weights_by_name["method_a"].overridden is True
    assert weights_by_name["method_b"].overridden is True
    # 0.5*100 + 0.5*200 = 150
    assert valuation.point_estimate == Decimal("150")


def test_manual_override_normalizes_unequal_weights() -> None:
    """Auditor passes 2:1, expect 2/3 and 1/3 normalized."""
    methods = [
        _fake("method_a", point=Decimal("100"), confidence=Decimal("0.5")),
        _fake("method_b", point=Decimal("100"), confidence=Decimal("0.5")),
    ]
    valuation = Triangulator(methods).value(
        _request(method_weights={"method_a": Decimal("2"), "method_b": Decimal("1")})
    )
    weights_by_name = {w.method_name: w.normalized_weight for w in valuation.weights}
    assert weights_by_name["method_a"] == Decimal("2") / Decimal("3")
    assert weights_by_name["method_b"] == Decimal("1") / Decimal("3")


def test_manual_override_unknown_name_raises() -> None:
    methods = [_fake("method_a")]
    with pytest.raises(ValueError, match="Unknown method weight key"):
        Triangulator(methods).value(_request(method_weights={"nonexistent": Decimal("1")}))


def test_manual_override_zero_sum_raises() -> None:
    methods = [_fake("method_a"), _fake("method_b")]
    with pytest.raises(ValueError, match="must sum > 0"):
        Triangulator(methods).value(
            _request(method_weights={"method_a": Decimal("0"), "method_b": Decimal("0")})
        )


# ---------- All-zero-confidence fallback ----------


def test_all_zero_confidence_falls_back_to_equal_weights() -> None:
    methods = [
        _fake("method_a", point=Decimal("100"), confidence=Decimal("0")),
        _fake("method_b", point=Decimal("200"), confidence=Decimal("0")),
    ]
    valuation = Triangulator(methods).value(_request())
    assert all(w.normalized_weight == Decimal("0.5") for w in valuation.weights)
    assert all(w.raw_confidence == Decimal("0") for w in valuation.weights)
    assert all(not w.overridden for w in valuation.weights)
    # 0.5*100 + 0.5*200 = 150
    assert valuation.point_estimate == Decimal("150")


# ---------- Dispersion flag boundary ----------


def test_dispersion_flag_above_threshold() -> None:
    """point=100, low=49, high=100 → dispersion=0.51 → flag True."""
    methods = [
        _fake(
            "only",
            point=Decimal("100"),
            low=Decimal("49"),
            high=Decimal("100"),
            confidence=Decimal("0.5"),
        ),
    ]
    valuation = Triangulator(methods).value(_request())
    assert valuation.dispersion == Decimal("0.51")
    assert valuation.dispersion_flag is True


def test_dispersion_flag_below_threshold() -> None:
    """point=100, low=51, high=100 → dispersion=0.49 → flag False."""
    methods = [
        _fake(
            "only",
            point=Decimal("100"),
            low=Decimal("51"),
            high=Decimal("100"),
            confidence=Decimal("0.5"),
        ),
    ]
    valuation = Triangulator(methods).value(_request())
    assert valuation.dispersion == Decimal("0.49")
    assert valuation.dispersion_flag is False


# ---------- No applicable method ----------


def test_no_applicable_method_raises() -> None:
    methods = [_fake("inapplicable", applicable=False)]
    with pytest.raises(NoApplicableMethodError):
        Triangulator(methods).value(_request())


def test_inapplicable_methods_are_filtered_out() -> None:
    methods = [
        _fake("skip_me", applicable=False, point=Decimal("999")),
        _fake(
            "include_me",
            applicable=True,
            point=Decimal("100"),
            low=Decimal("80"),
            high=Decimal("120"),
            confidence=Decimal("0.5"),
        ),
    ]
    valuation = Triangulator(methods).value(_request())
    method_names = {r.method_name for r in valuation.method_results}
    assert method_names == {"include_me"}
    assert valuation.point_estimate == Decimal("100")


def test_skipped_methods_recorded_with_reason() -> None:
    """Inapplicable methods should land in `skipped_methods` with the method's
    own `inapplicability_reason` — not silently dropped."""
    methods = [
        _fake("skip_me", applicable=False),
        _fake("include_me", applicable=True),
    ]
    valuation = Triangulator(methods).value(_request())
    assert [s.method_name for s in valuation.skipped_methods] == ["skip_me"]
    assert valuation.skipped_methods[0].reason == "fake reason for skip_me"


def test_skipped_methods_empty_when_all_applicable() -> None:
    methods = [_fake("a"), _fake("b")]
    valuation = Triangulator(methods).value(_request())
    assert valuation.skipped_methods == []


# ---------- Generated_at present ----------


def test_generated_at_within_5_seconds_of_now() -> None:
    methods = [_fake("method_a")]
    before = datetime.now(UTC)
    valuation = Triangulator(methods).value(_request())
    after = datetime.now(UTC)
    assert before <= valuation.generated_at <= after
    # Sanity: timezone-aware
    assert valuation.generated_at.tzinfo is not None


# ---------- Per-method outlier detection ----------


def test_no_outliers_when_fewer_than_three_methods() -> None:
    methods = [
        _fake("method_a", point=Decimal("100")),
        _fake("method_b", point=Decimal("1000")),
    ]
    valuation = Triangulator(methods).value(_request())
    assert valuation.outlier_method_names == []


def test_outliers_above_2x_median_flagged() -> None:
    methods = [
        _fake("method_a", point=Decimal("100")),
        _fake("method_b", point=Decimal("100")),
        _fake("method_c", point=Decimal("250")),
    ]
    valuation = Triangulator(methods).value(_request())
    assert valuation.outlier_method_names == ["method_c"]


def test_outliers_below_half_median_flagged() -> None:
    methods = [
        _fake("method_a", point=Decimal("40")),
        _fake("method_b", point=Decimal("100")),
        _fake("method_c", point=Decimal("100")),
    ]
    valuation = Triangulator(methods).value(_request())
    assert valuation.outlier_method_names == ["method_a"]


def test_no_outliers_when_all_close() -> None:
    methods = [
        _fake("method_a", point=Decimal("95")),
        _fake("method_b", point=Decimal("100")),
        _fake("method_c", point=Decimal("105")),
    ]
    valuation = Triangulator(methods).value(_request())
    assert valuation.outlier_method_names == []


def test_zero_median_returns_empty_list() -> None:
    methods = [
        _fake("method_a", point=Decimal("0"), low=Decimal("0"), high=Decimal("0")),
        _fake("method_b", point=Decimal("0"), low=Decimal("0"), high=Decimal("0")),
        _fake("method_c", point=Decimal("0"), low=Decimal("0"), high=Decimal("0")),
    ]
    valuation = Triangulator(methods).value(_request())
    assert valuation.outlier_method_names == []


def test_outlier_method_names_preserves_input_order() -> None:
    methods = [
        _fake("A", point=Decimal("400")),
        _fake("B", point=Decimal("100")),
        _fake("C", point=Decimal("10")),
    ]
    valuation = Triangulator(methods).value(_request())
    assert valuation.outlier_method_names == ["A", "C"]
