"""JSON report writer.

`DecimalStr` (in `vc_audit.models.types`) carries a `PlainSerializer(when_used="json")`
that converts Decimals to strings, so `model_dump_json` already preserves precision
through round-trips. No custom encoder required.
"""

from pathlib import Path

from vc_audit.models import TriangulatedValuation


def write_json(valuation: TriangulatedValuation, path: Path) -> Path:
    """Write `valuation` as pretty-printed JSON. Returns the path written."""
    payload = valuation.model_dump_json(indent=2)
    path.write_text(payload, encoding="utf-8")
    return path


def to_json_str(valuation: TriangulatedValuation) -> str:
    """String variant for tests / API responses."""
    return valuation.model_dump_json(indent=2)
