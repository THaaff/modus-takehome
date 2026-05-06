"""Shared Pydantic field types.

`DecimalStr` is `Decimal` with JSON serialization forced to a string. This preserves
precision through round-trips — Pydantic v2's default emits Decimal as a JSON number,
which can lose precision on re-parse. For an audit artifact, that's the wrong default.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

DecimalStr = Annotated[
    Decimal,
    PlainSerializer(lambda v: str(v), return_type=str, when_used="json"),
]
