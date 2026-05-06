"""Named assumption emitted by a valuation method for the audit trail."""

from pydantic import BaseModel, ConfigDict


class Assumption(BaseModel):
    """A named choice the method made, with the reason it made it."""

    model_config = ConfigDict(frozen=True)

    name: str  # e.g. "EV/Revenue multiple"
    value: str  # stringified for an audit trail (e.g. "8.2x")
    rationale: str
