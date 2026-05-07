"""Triangulator: combines applicable method outputs into a single audit artifact.

Workflow:
1. Filter to methods whose `is_applicable(request)` returns True.
2. Run each — order preserved from the registered list.
3. Compute weights:
   - If `request.method_weights` is provided, validate every key matches an applicable
     method, then normalize the supplied weights. Marked `overridden=True`.
   - Else, normalize by raw confidence. Marked `overridden=False`. If all confidences
     are zero, fall back to equal weights (signal: raw_confidence=0 with non-zero
     normalized_weight on every entry).
4. Synthesize:
   - point_estimate = Σ weight × point per method
   - range_low/high = elementwise min/max across method results
   - dispersion = (high − low) / point (or 0 if point == 0)
   - dispersion_flag = dispersion > TriangulatedValuation.dispersion_threshold()

Raises `NoApplicableMethodError` if no method applies, and `ValueError` for malformed
manual overrides.
"""

from datetime import UTC, datetime
from decimal import Decimal

from vc_audit.methods import NoApplicableMethodError, ValuationMethod
from vc_audit.models import (
    MethodResult,
    MethodWeight,
    SkippedMethod,
    TriangulatedValuation,
    ValuationRequest,
)


class Triangulator:
    """Combine the outputs of multiple applicable `ValuationMethod`s."""

    def __init__(self, methods: list[ValuationMethod]) -> None:
        self._methods = list(methods)

    def value(self, request: ValuationRequest) -> TriangulatedValuation:
        applicable: list[ValuationMethod] = []
        skipped: list[SkippedMethod] = []
        for method in self._methods:
            if method.is_applicable(request):
                applicable.append(method)
            else:
                skipped.append(
                    SkippedMethod(
                        method_name=method.name,
                        reason=method.inapplicability_reason(request),
                    )
                )
        if not applicable:
            raise NoApplicableMethodError(
                f"No registered method applies to request for company={request.company.name!r}"
            )

        results = [m.value(request) for m in applicable]
        outlier_method_names = self._compute_outliers(results)
        weights = self._compute_weights(results, request)

        # `weights` is built in lockstep with `results`; pair by index.
        point = sum(
            (w.normalized_weight * r.point_estimate for w, r in zip(weights, results, strict=True)),
            Decimal(0),
        )
        low = min(r.low for r in results)
        high = max(r.high for r in results)
        dispersion = ((high - low) / point) if point > 0 else Decimal(0)
        dispersion_flag = dispersion > TriangulatedValuation.dispersion_threshold()

        return TriangulatedValuation(
            company=request.company,
            as_of_date=request.as_of_date,
            point_estimate=point,
            range_low=low,
            range_high=high,
            dispersion=dispersion,
            dispersion_flag=dispersion_flag,
            outlier_method_names=outlier_method_names,
            method_results=results,
            skipped_methods=skipped,
            weights=weights,
            request=request,
            generated_at=datetime.now(UTC),
        )

    @staticmethod
    def _compute_outliers(results: list[MethodResult]) -> list[str]:
        if len(results) < 3:
            return []
        sorted_points = sorted(r.point_estimate for r in results)
        n = len(sorted_points)
        if n % 2 == 1:
            median = sorted_points[n // 2]
        else:
            median = (sorted_points[n // 2 - 1] + sorted_points[n // 2]) / Decimal(2)
        if median == 0:
            return []
        upper = 2 * median
        lower = median / 2
        return [
            r.method_name for r in results if r.point_estimate > upper or r.point_estimate < lower
        ]

    @staticmethod
    def _compute_weights(
        results: list[MethodResult], request: ValuationRequest
    ) -> list[MethodWeight]:
        applicable_names = {r.method_name for r in results}

        if request.method_weights is not None:
            # Validate keys before doing any math — auditor errors should be loud.
            for key in request.method_weights:
                if key not in applicable_names:
                    raise ValueError(f"Unknown method weight key: {key}")
            # Sum only the supplied weights for applicable methods (already validated above).
            supplied = request.method_weights
            total = sum(
                (supplied[r.method_name] for r in results if r.method_name in supplied),
                Decimal(0),
            )
            if total == 0:
                raise ValueError("method_weights must sum > 0")
            return [
                MethodWeight(
                    method_name=r.method_name,
                    raw_confidence=r.confidence,
                    normalized_weight=(
                        supplied[r.method_name] / total if r.method_name in supplied else Decimal(0)
                    ),
                    overridden=True,
                )
                for r in results
            ]

        total_conf = sum((r.confidence for r in results), Decimal(0))
        if total_conf == 0:
            # Equal-weight fallback. Signal is implicit in raw_confidence=0 +
            # normalized_weight>0 on each entry — see module docstring.
            n = Decimal(len(results))
            return [
                MethodWeight(
                    method_name=r.method_name,
                    raw_confidence=r.confidence,
                    normalized_weight=Decimal(1) / n,
                    overridden=False,
                )
                for r in results
            ]
        return [
            MethodWeight(
                method_name=r.method_name,
                raw_confidence=r.confidence,
                normalized_weight=r.confidence / total_conf,
                overridden=False,
            )
            for r in results
        ]
