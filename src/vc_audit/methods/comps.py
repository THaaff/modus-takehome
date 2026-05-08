"""Public-comps valuation method.

Implements the EV/Revenue (and optionally EV/EBITDA) median-multiple approach against a
sector-matched peer set drawn from a `CompsProvider`. The applicability gate intentionally
queries the provider — empty sectors are skipped at the Triangulator level rather than
producing a degenerate `MethodResult`.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar

from vc_audit.data.comps_provider import Comp, CompsProvider
from vc_audit.methods.base import ValuationMethod
from vc_audit.models import (
    Assumption,
    Citation,
    MethodResult,
    ValuationRequest,
)


def _percentile(values: list[Decimal], pct: Decimal) -> Decimal:
    """Linear-interpolation percentile on a sorted copy of `values`.

    `pct` is in [0, 1]. Mirrors numpy's default behavior closely enough for our purposes
    while keeping numpy out of the dependency graph. Values must be non-empty.
    """
    if not values:
        raise ValueError("_percentile requires at least one value")
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    # Position on a 0..(n-1) index axis.
    pos = pct * Decimal(len(sorted_vals) - 1)
    lower_idx = int(pos)  # truncates toward zero; pos >= 0 here
    upper_idx = min(lower_idx + 1, len(sorted_vals) - 1)
    frac = pos - Decimal(lower_idx)
    lower = sorted_vals[lower_idx]
    upper = sorted_vals[upper_idx]
    return lower + (upper - lower) * frac


def _format_multiple(m: Decimal) -> str:
    """Render a multiple like `8.2x` for assumption strings."""
    return f"{m.quantize(Decimal('0.01'))}x"


class CompsMethod(ValuationMethod):
    """Median EV/Revenue (and EV/EBITDA when available) against a sector peer set."""

    name: ClassVar[str] = "comps"
    description: ClassVar[str] = (
        "Sector-peer median EV/Revenue (and EV/EBITDA when available) applied to the "
        "target's revenue and EBITDA."
    )
    required_inputs: ClassVar[tuple[str, ...]] = ("company.sector", "revenue")

    def __init__(self, comps_provider: CompsProvider) -> None:
        # Stored as the structural Protocol; concrete type is irrelevant past this point.
        self._provider = comps_provider

    # ------------------------------------------------------------------ applicability

    def is_applicable(self, request: ValuationRequest) -> bool:
        """Need a sector, a revenue figure, and at least one peer in that sector."""
        sector = request.company.sector
        if sector is None:
            return False
        if request.revenue is None:
            return False
        peers = self._provider.get_comps(sector)
        return len(peers) >= 1

    def inapplicability_reason(self, request: ValuationRequest) -> str:
        """Pinpoint which input — sector, revenue, or peer set — caused the skip."""
        sector = request.company.sector
        if sector is None:
            return "Company sector is missing — comps requires a sector to match peers."
        if request.revenue is None:
            return "Target revenue is missing — comps applies an EV/Revenue multiple."
        peers = self._provider.get_comps(sector)
        if not peers:
            return f"No peers found in the comps universe for sector {sector!r}."
        return super().inapplicability_reason(request)

    # ------------------------------------------------------------------ valuation

    def value(self, request: ValuationRequest) -> MethodResult:
        """Compute the comps-implied valuation. Caller must have checked `is_applicable`."""
        # `is_applicable` guarantees these are set; assert for the type checker.
        sector = request.company.sector
        target_revenue = request.revenue
        assert sector is not None
        assert target_revenue is not None

        peers = self._provider.get_comps(sector)
        n_peers = len(peers)

        # EV/Revenue: every peer with non-zero revenue contributes.
        ev_rev_multiples: list[Decimal] = [
            p.enterprise_value / p.revenue for p in peers if p.revenue > 0
        ]

        # EV/EBITDA: only when target has positive EBITDA AND at least 2 peers do.
        target_ebitda = request.ebitda
        ebitda_peers: list[Comp] = [p for p in peers if p.ebitda is not None and p.ebitda > 0]
        use_ebitda = target_ebitda is not None and target_ebitda > 0 and len(ebitda_peers) >= 2
        ev_ebitda_multiples: list[Decimal] = (
            [p.enterprise_value / p.ebitda for p in ebitda_peers if p.ebitda is not None]
            if use_ebitda
            else []
        )

        rev_estimate = self._estimate_from_multiples(ev_rev_multiples, target_revenue)
        ebitda_estimate: tuple[Decimal, Decimal, Decimal] | None = None
        if use_ebitda and target_ebitda is not None:
            ebitda_estimate = self._estimate_from_multiples(ev_ebitda_multiples, target_ebitda)

        # Combine: average element-wise when both are present, else use the live one.
        if rev_estimate is not None and ebitda_estimate is not None:
            point = (rev_estimate[0] + ebitda_estimate[0]) / Decimal(2)
            low = (rev_estimate[1] + ebitda_estimate[1]) / Decimal(2)
            high = (rev_estimate[2] + ebitda_estimate[2]) / Decimal(2)
        elif rev_estimate is not None:
            point, low, high = rev_estimate
        elif ebitda_estimate is not None:
            point, low, high = ebitda_estimate
        else:
            # Should only fire if every peer had zero revenue — not realistic, but safe.
            point = low = high = Decimal(0)

        # Confidence: peer-count proxy, clamped at 1.0.
        confidence = min(Decimal(1), Decimal(n_peers) / Decimal(8))

        # ------- Assumptions
        assumptions: list[Assumption] = []

        if rev_estimate is not None and ebitda_estimate is not None:
            metric_used = "EV/Revenue and EV/EBITDA"
        elif rev_estimate is not None:
            metric_used = "EV/Revenue"
        elif ebitda_estimate is not None:
            metric_used = "EV/EBITDA"
        else:
            metric_used = "none"
        assumptions.append(
            Assumption(
                name="Multiples used",
                value=metric_used,
                rationale=(
                    "EV/Revenue applied whenever target revenue and >=1 peer revenue "
                    "are present; EV/EBITDA additionally applied when target EBITDA "
                    "and >=2 peers' EBITDA are positive."
                ),
            )
        )

        if rev_estimate is not None:
            median_ev_rev = _percentile(ev_rev_multiples, Decimal("0.5"))
            assumptions.append(
                Assumption(
                    name="EV/Revenue median multiple",
                    value=_format_multiple(median_ev_rev),
                    rationale="Median across sector peers; 25/75 percentile drives low/high.",
                )
            )
        if ebitda_estimate is not None:
            median_ev_ebitda = _percentile(ev_ebitda_multiples, Decimal("0.5"))
            assumptions.append(
                Assumption(
                    name="EV/EBITDA median multiple",
                    value=_format_multiple(median_ev_ebitda),
                    rationale="Median across sector peers with positive EBITDA.",
                )
            )

        assumptions.append(
            Assumption(
                name="Peer count",
                value=str(n_peers),
                rationale=(
                    "Number of sector-matched peers found in the comps universe; "
                    "drives confidence via min(1, n/8)."
                ),
            )
        )

        if n_peers < 3:
            assumptions.append(
                Assumption(
                    name="Sparse peer set",
                    value=f"{n_peers} peer(s) — below typical threshold of 3",
                    rationale=(
                        "Median multiple computed from a small sample; "
                        "confidence reduced via min(1, n/8) formula. "
                        "Triangulator weights this method accordingly."
                    ),
                )
            )

        # ------- Citations
        citations = [
            Citation(
                source=f"CompsProvider:{getattr(self._provider, 'source_id', 'unknown')}",
                description=(
                    f"Peer set: {', '.join(sorted(p.ticker for p in peers))} "
                    f"(sector={sector}, n={n_peers})"
                ),
                retrieved_at=datetime.now(UTC),
                url=None,
            )
        ]

        return MethodResult(
            method_name=self.name,
            point_estimate=point,
            low=low,
            high=high,
            confidence=confidence,
            assumptions=assumptions,
            citations=citations,
        )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _estimate_from_multiples(
        multiples: list[Decimal], driver: Decimal
    ) -> tuple[Decimal, Decimal, Decimal] | None:
        """Return (point, low, high) implied valuations from a multiples list.

        `driver` is the target's revenue (or EBITDA). Returns `None` when `multiples`
        is empty so the caller can fall back to the other metric.
        """
        if not multiples:
            return None
        median = _percentile(multiples, Decimal("0.5"))
        p25 = _percentile(multiples, Decimal("0.25"))
        p75 = _percentile(multiples, Decimal("0.75"))
        return (median * driver, p25 * driver, p75 * driver)
