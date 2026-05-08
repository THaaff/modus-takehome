"""Markdown report writer.

Renders a `TriangulatedValuation` as an audit-trail markdown report:
header → headline → per-method breakdown table + per-method detail blocks → echoed request.

Numeric formatting (units always labeled at the call site):
- Money values are in $M (millions of US dollars), rendered as `$1,234.56M` (always 2dp).
- Fractions in [0, 1] (confidence, weights) render as `12.34%`.
- Dispersion is a unitless ratio rendered as `1.0135` (not %, since it can exceed 100%
  and reads better as a multiplier of the point estimate).

Plain-text status markers ("(FLAG)", "(within tolerance)") are used in place of emoji.
"""

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from vc_audit._formatting import format_percent_rate
from vc_audit.models import (
    Assumption,
    Citation,
    DCFSensitivityGrid,
    MethodResult,
    MethodWeight,
    SkippedMethod,
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
        _skipped_methods(valuation),
        _request_appendix(valuation),
    ]
    return "\n\n".join(p for p in parts if p) + "\n"


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
    lines = [
        "## Headline",
        "",
        "_Money values are in $M (millions of US dollars). "
        "Confidence and weights are in [0, 1]. Dispersion is a unitless ratio._",
        "",
        f"- **Valuation point estimate:** {_currency(valuation.point_estimate)}",
        (
            f"- **Valuation range:** {_currency(valuation.range_low)} – "
            f"{_currency(valuation.range_high)}"
        ),
        f"- **Dispersion:** {_ratio(valuation.dispersion)} {flag}",
    ]
    if valuation.outlier_method_names:
        lines.append(f"- **Outlier methods:** {', '.join(valuation.outlier_method_names)}")
    return "\n".join(lines)


def _method_breakdown(valuation: TriangulatedValuation) -> str:
    weights_by_name = {w.method_name: w for w in valuation.weights}
    outlier_set = set(valuation.outlier_method_names)
    header = (
        "| Method | Point ($M) | Low ($M) | High ($M) "
        "| Confidence | Weight | Overridden | Outlier |"
    )
    table_lines = [
        "## Method breakdown",
        "",
        header,
        "|---|---|---|---|---|---|---|---|",
    ]
    for result in valuation.method_results:
        weight = weights_by_name[result.method_name]
        is_outlier = result.method_name in outlier_set
        table_lines.append(_method_row(result, weight, is_outlier))

    detail_blocks = [_method_detail(r) for r in valuation.method_results]
    return "\n".join(table_lines) + "\n\n" + "\n\n".join(detail_blocks)


def _method_row(result: MethodResult, weight: MethodWeight, is_outlier: bool) -> str:
    overridden = "yes" if weight.overridden else "no"
    outlier = "yes" if is_outlier else ""
    return (
        f"| {result.method_name} "
        f"| {_currency(result.point_estimate)} "
        f"| {_currency(result.low)} "
        f"| {_currency(result.high)} "
        f"| {_percent(result.confidence)} "
        f"| {_percent(weight.normalized_weight)} "
        f"| {overridden} "
        f"| {outlier} |"
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
    lines.append(
        "_Upstream data sources this method drew from. "
        "Format: `Source: identifier — description (retrieved timestamp)`._"
    )
    if result.citations:
        lines.extend(_citation_line(c) for c in result.citations)
    else:
        lines.append("- (none)")
    if result.dcf_sensitivity is not None:
        lines.append("")
        lines.append(_sensitivity_grid_block(result.dcf_sensitivity))
    return "\n".join(lines)


def _sensitivity_grid_block(grid: DCFSensitivityGrid) -> str:
    """Render the 3x3 grid as a markdown table.

    Rows are perturbed discount rates; columns are perturbed terminal-growth rates.
    The center cell (dr=0, dg=0) is bolded so reviewers can read the as-supplied
    EV at a glance. Skipped cells render as ``— (skipped)``.
    """
    n_growth = len(grid.terminal_growth_deltas)
    growths = [grid.center_terminal_growth + dg for dg in grid.terminal_growth_deltas]
    rates = [grid.center_discount_rate + dr for dr in grid.discount_rate_deltas]
    growth_header = " | ".join(format_percent_rate(g) for g in growths)
    header = f"| discount rate \\ terminal growth | {growth_header} |"
    sep = "|---" * (n_growth + 1) + "|"
    lines = [
        "**Sensitivity grid (EV in $M):**",
        "",
        "_Rows: perturbed discount rate (center ±1pp). Columns: perturbed terminal "
        "growth (center ±0.5pp). Center cell (auditor-supplied rates) is **bold**._",
        "",
        header,
        sep,
    ]
    for row_idx, r_rate in enumerate(rates):
        cells_in_row = grid.cells[row_idx * n_growth : (row_idx + 1) * n_growth]
        rendered_cells: list[str] = []
        for col_idx, cell in enumerate(cells_in_row):
            is_center = grid.discount_rate_deltas[row_idx] == Decimal(
                0
            ) and grid.terminal_growth_deltas[col_idx] == Decimal(0)
            rendered_cells.append(_format_grid_cell(cell.enterprise_value, is_center))
        lines.append(f"| {format_percent_rate(r_rate)} | " + " | ".join(rendered_cells) + " |")
    return "\n".join(lines)


def _format_grid_cell(ev: Decimal | None, is_center: bool) -> str:
    if ev is None:
        return "— (skipped)"
    rendered = _currency(ev)
    return f"**{rendered}**" if is_center else rendered


def _assumption_line(a: Assumption) -> str:
    return f"- **{a.name}:** {a.value} — {a.rationale}"


def _citation_line(c: Citation) -> str:
    url = f" ({c.url})" if c.url else ""
    namespace, _, identifier = c.source.partition(":")
    rendered_source = f"**{namespace}:** {identifier}" if identifier else f"**{namespace}**"
    return f"- {rendered_source} — {c.description} (retrieved {c.retrieved_at.isoformat()}){url}"


def _skipped_methods(valuation: TriangulatedValuation) -> str:
    """Render the list of methods that didn't run, with the reason for each.

    Returns "" when nothing was skipped so the section is omitted entirely from
    the report rather than showing an empty heading.
    """
    if not valuation.skipped_methods:
        return ""
    lines = [
        "## Skipped methods",
        "",
        "_Registered methods that did not run for this request, and why. "
        "Useful for explaining why the triangulated estimate is leaning on a subset._",
        "",
    ]
    lines.extend(_skipped_line(s) for s in valuation.skipped_methods)
    return "\n".join(lines)


def _skipped_line(s: SkippedMethod) -> str:
    return f"- **{s.method_name}:** {s.reason}"


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
    """Render a $M amount as ``$1,234.56M`` — always 2dp, thousands-separated.

    Money is in millions of US dollars by convention (see the headline's units note);
    the ``M`` suffix makes that explicit at every call site.
    """
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"${format(quantized, ',f')}M"


def _percent(value: Decimal) -> str:
    """Render a [0, 1] fraction as ``12.34%`` for confidence/weights."""
    return f"{float(value):.2%}"


def _ratio(value: Decimal) -> str:
    """Render a unitless ratio (e.g., dispersion) as ``1.0135``.

    Kept as a plain ratio rather than a percent because dispersion can exceed 100%
    and "101.35%" reads worse than "1.0135 (= ratio of high–low spread to point)".
    """
    quantized = value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return format(quantized, "f")
