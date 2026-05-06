"""Public-comps universe provider interface.

Real implementations could pull from Yahoo Finance, Bloomberg, internal datasets, etc.
The mock in T3a reads from a hand-curated JSON fixture.
"""

from datetime import date
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from vc_audit.models.types import DecimalStr


class Comp(BaseModel):
    """A single public comparable company."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    sector: str
    revenue: DecimalStr
    ebitda: DecimalStr | None = None
    enterprise_value: DecimalStr


@runtime_checkable
class CompsProvider(Protocol):
    """Returns comps for a sector. Structural typing — no inheritance required."""

    def get_comps(self, sector: str) -> list[Comp]: ...


class _FixtureFile(BaseModel):
    """Internal Pydantic schema for the on-disk comp-universe fixture."""

    model_config = ConfigDict(frozen=True)

    as_of: date
    source_id: str
    comps: list[Comp]


_DEFAULT_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "comp_universe.json"


class MockCompsProvider:
    """File-backed `CompsProvider`. Loads the universe once at construction.

    The fixture path defaults to `data/fixtures/comp_universe.json`. Sector matching is
    case-sensitive and exact — adjacent-sector relaxation is intentionally out of scope
    for the mock (see PLAN.md §5.2).
    """

    def __init__(self, fixture_path: Path | None = None) -> None:
        path = fixture_path if fixture_path is not None else _DEFAULT_FIXTURE_PATH
        raw = path.read_text(encoding="utf-8")
        fixture = _FixtureFile.model_validate_json(raw)
        self.as_of: date = fixture.as_of
        self.source_id: str = fixture.source_id
        self._comps: list[Comp] = list(fixture.comps)

    def get_comps(self, sector: str) -> list[Comp]:
        """Return comps whose `sector` exactly matches `sector` (case-sensitive)."""
        return [c for c in self._comps if c.sector == sector]
