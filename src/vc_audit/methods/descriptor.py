"""Self-describing metadata for valuation methods.

Each `ValuationMethod` subclass exposes a `describe()` classmethod that returns a
`MethodDescriptor` — used by `GET /methods` and `vc-audit methods` so the API and CLI
agree on what each strategy needs without hardcoding the list at the call site.
"""

from pydantic import BaseModel


class MethodDescriptor(BaseModel):
    """Auditor-facing metadata for a single valuation method."""

    name: str
    description: str
    required_inputs: list[str]
