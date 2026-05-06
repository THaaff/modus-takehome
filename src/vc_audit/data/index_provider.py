"""Public market-index price provider interface.

Used by the Last-Round method to compute the index return between the round date and
the as-of date. Real implementations could pull from FRED, Yahoo, etc.; the mock in
T3b reads NASDAQ history from a JSON fixture.
"""

import json
from bisect import bisect_right
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class MarketIndexProvider(Protocol):
    """Anything that can return an index closing level on a given date."""

    def get_price(self, index: str, on: date) -> Decimal: ...


class MockMarketIndexProvider:
    """File-backed `MarketIndexProvider` reading monthly closes from a JSON fixture.

    Lookup uses a nearest-prior-anchor strategy: for a requested date, return the close
    of the latest entry on or before that date. With monthly granularity this is the
    industry-standard backstop and avoids the spurious precision of interpolation —
    we surface the heuristic explicitly via the LastRound method's assumptions.
    """

    source_id: str = "mock_nasdaq_v1"

    def __init__(self, fixture_path: Path | None = None) -> None:
        if fixture_path is None:
            fixture_path = Path(__file__).parent / "fixtures" / "nasdaq_history.json"
        with fixture_path.open() as fh:
            raw: dict[str, list[dict[str, str]]] = json.load(fh)
        # Internal storage: {index: [(date, close), ...] sorted ascending by date}.
        self._series: dict[str, list[tuple[date, Decimal]]] = {
            index: sorted(
                ((date.fromisoformat(row["date"]), Decimal(row["close"])) for row in rows),
                key=lambda pair: pair[0],
            )
            for index, rows in raw.items()
        }

    def get_price(self, index: str, on: date) -> Decimal:
        """Return the close on `on` using a nearest-prior-anchor lookup.

        Raises `KeyError` if `index` is unknown or if `on` precedes the earliest entry
        for that index (i.e., the series cannot back-stop the request).
        """
        if index not in self._series:
            raise KeyError(f"Unknown index: {index}")
        rows = self._series[index]
        # Find the rightmost entry with date <= on. bisect_right on the date-only
        # projection gives us insertion point; subtract one to get the anchor.
        dates = [pair[0] for pair in rows]
        idx = bisect_right(dates, on) - 1
        if idx < 0:
            raise KeyError(f"No {index} price on or before {on}")
        return rows[idx][1]

    @property
    def series_range(self) -> tuple[date, date]:
        """Min/max date covered across all loaded indices. Useful for citation construction."""
        all_dates = [pair[0] for rows in self._series.values() for pair in rows]
        return min(all_dates), max(all_dates)
