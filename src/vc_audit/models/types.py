"""Shared Pydantic field types.

`DecimalStr` is `Decimal` with JSON serialization forced to a string. This preserves
precision through round-trips — Pydantic v2's default emits Decimal as a JSON number,
which can lose precision on re-parse. For an audit artifact, that's the wrong default.

`Money2dp` and `Fraction4dp` are display-rounded variants for *output* fields. Internal
math stays full-precision; only the JSON serialization quantizes. Inputs (the echoed
request) keep `DecimalStr` so a replay is byte-for-byte identical.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import PlainSerializer

DecimalStr = Annotated[
    Decimal,
    PlainSerializer(lambda v: str(v), return_type=str, when_used="json"),
]


def _quantize_money(v: Decimal) -> str:
    """Quantize to 2dp ($0.01M = $10K precision) for display."""
    return str(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _quantize_fraction(v: Decimal) -> str:
    """Quantize to 4dp; small enough for weights/confidence/dispersion without noise."""
    return str(v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


# Money values, expressed in $M (millions of US dollars). 2dp = $10K precision.
Money2dp = Annotated[
    Decimal,
    PlainSerializer(_quantize_money, return_type=str, when_used="json"),
]

# Unitless fractions in [0, 1] (confidence, weights) or ratios (dispersion). 4dp.
Fraction4dp = Annotated[
    Decimal,
    PlainSerializer(_quantize_fraction, return_type=str, when_used="json"),
]
