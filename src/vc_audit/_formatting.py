"""Shared rendering helpers used by both methods (assumption strings) and reports.

These are intentionally trivial; they live here to keep a single canonical format
across the DCF method's own assumption rationale and the markdown report's
sensitivity-grid header. Drift between the two would be a silent audit bug.
"""

from decimal import ROUND_HALF_UP, Decimal


def format_percent_rate(rate: Decimal) -> str:
    """Render an annual rate (e.g., ``Decimal('0.115')``) as ``"11.50%"``.

    Always 2dp with ``ROUND_HALF_UP``. The ``%`` suffix disambiguates
    from raw decimals at the call site.
    """
    return f"{(rate * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):f}%"
