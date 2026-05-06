"""Public-comps universe provider interface.

Real implementations could pull from Yahoo Finance, Bloomberg, internal datasets, etc.
The mock in T3a reads from a hand-curated JSON fixture.
"""

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
