"""Markdown report writer.

Renders a `TriangulatedValuation` as an audit-trail markdown report:
header → headline → per-method breakdown table + per-method detail blocks → echoed request.

Numeric formatting:
- Currency uses thousands-separator formatting on a `Decimal` value (`format(d, ',f')`).
- Percentages (dispersion, confidence, weight) use `f"{float(v):.2%}"` — float coercion
  is acceptable for display only.

Plain-text status markers ("(FLAG)", "(within tolerance)") are used in place of emoji.
"""

from decimal import Decimal
from pathlib import Path

from vc_audit.models import (
    Assumption,
    Citation,
    MethodResult,
    MethodWeight,
    TriangulatedValuation,
)


def write_markdown(valuation: TriangulatedValuation, path: Path) -> Path:
    """Write the markdown report to `path`. Returns the path written."""
    content = to_markdown_str(valuation)
    path.write_text(content, encoding="utf-8")
    return path


def to_markdown_str(valuation: TriangulatedValuation) -> str:
    """Render the markdown report as a string."""
    parts = [
        _header(valuation),
        _headline(valuation),
        _method_breakdown(valuation),
        _request_appendix(valuation),
    ]
    return "\n\n".join(parts) + "\n"


# ---------- Section renderers ----------


def _header(valuation: TriangulatedValuation) -> str:
    lines = [
        f"# VC Audit Report — {valuation.company.name}",
        "",
        f"**As-of date:** {valuation.as_of_date.isoformat()}",
        f"**Generated:** {valuation.generated_at.isoformat()}",
    ]
    if valuation.company.sector:
        lines.append(f"**Sector:** {valuation.company.sector}")
    return "\n".join(lines)


def _headline(valuation: TriangulatedValuation) -> str:
    flag = "(FLAG)" if valuation.dispersion_flag else "(within tolerance)"
    return "\n".join(
        [
            "## Headline",
            "",
            f"- **Point estimate:** {_currency(valuation.point_estimate)}",
            f"- **Range:** {_currency(valuation.range_low)} – {_currency(valuation.range_high)}",
            f"- **Dispersion:** {_percent(valuation.dispersion)} {flag}",
        ]
    )


def _method_breakdown(valuation: TriangulatedValuation) -> str:
    weights_by_name = {w.method_name: w for w in valuation.weights}
    table_lines = [
        "## Method breakdown",
        "",
        "| Method | Point | Low | High | Confidence | Weight | Overridden |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in valuation.method_results:
        weight = weights_by_name[result.method_name]
        table_lines.append(_method_row(result, weight))

    detail_blocks = [_method_detail(r) for r in valuation.method_results]
    return "\n".join(table_lines) + "\n\n" + "\n\n".join(detail_blocks)


def _method_row(result: MethodResult, weight: MethodWeight) -> str:
    overridden = "yes" if weight.overridden else "no"
    return (
        f"| {result.method_name} "
        f"| {_currency(result.point_estimate)} "
        f"| {_currency(result.low)} "
        f"| {_currency(result.high)} "
        f"| {_percent(result.confidence)} "
        f"| {_percent(weight.normalized_weight)} "
        f"| {overridden} |"
    )


def _method_detail(result: MethodResult) -> str:
    lines = [f"### {result.method_name}", ""]
    if result.notes:
        lines.append(f"_{result.notes}_")
        lines.append("")
    lines.append("**Assumptions:**")
    if result.assumptions:
        lines.extend(_assumption_line(a) for a in result.assumptions)
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("**Citations:**")
    if result.citations:
        lines.extend(_citation_line(c) for c in result.citations)
    else:
        lines.append("- (none)")
    return "\n".join(lines)


def _assumption_line(a: Assumption) -> str:
    return f"- **{a.name}:** {a.value} — {a.rationale}"


def _citation_line(c: Citation) -> str:
    url = f" ({c.url})" if c.url else ""
    return f"- {c.source} — {c.description} (retrieved {c.retrieved_at.isoformat()}){url}"


def _request_appendix(valuation: TriangulatedValuation) -> str:
    return "\n".join(
        [
            "## Request (echoed)",
            "",
            "```json",
            valuation.request.model_dump_json(indent=2),
            "```",
        ]
    )


# ---------- Formatting helpers ----------


def _currency(value: Decimal) -> str:
    """Render a Decimal as a $-prefixed amount with thousands separators.

    Trailing zeros after the decimal are stripped where they don't change precision
    (e.g. ``100.00 → 100``, ``100.50 → 100.5``).
    """
    normalized = value.normalize() if value == value.to_integral_value() else value
    # `format(Decimal, ',f')` adds thousands separators without scientific notation.
    text = format(normalized, ",f")
    # Strip trailing zeros after a decimal point (without affecting integer values).
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"${text}"


def _percent(value: Decimal) -> str:
    return f"{float(value):.2%}"
