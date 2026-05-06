"""Public market-index price provider interface.

Used by the Last-Round method to compute the index return between the round date and
the as-of date. Real implementations could pull from FRED, Yahoo, etc.; the mock in
T3b reads NASDAQ history from a JSON fixture.
"""

from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable


@runtime_checkable
class MarketIndexProvider(Protocol):
    """Anything that can return an index closing level on a given date."""

    def get_price(self, index: str, on: date) -> Decimal: ...
