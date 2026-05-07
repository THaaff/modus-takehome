"""Typer CLI entrypoint.

Three commands, all stateless and deterministic in lockstep with the API:

- ``vc-audit value``   — run triangulation on a request JSON.
- ``vc-audit methods`` — print method descriptors as JSON.
- ``vc-audit example`` — print the bundled sample request.

The default for ``value`` is JSON to stdout (pipe-friendly). Pass ``--output-dir`` to
write artifacts to disk instead — that's the auditor-trail mode.
"""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from vc_audit.engine import build_default_triangulator, default_method_descriptors
from vc_audit.methods import NoApplicableMethodError
from vc_audit.models import ValuationRequest
from vc_audit.reports import to_json_str, to_markdown_str, write_json, write_markdown


class Format(StrEnum):
    """Output format options. Mirror the API ``?format=`` query param."""

    json = "json"
    markdown = "markdown"
    both = "both"


app = typer.Typer(
    help="VC Audit Tool — fair-value triangulation for private portfolio companies.",
    no_args_is_help=True,
)


# Resolve relative to the project root (src/ sibling). Works for `uv run` and editable
# installs; non-editable installs would need package data, which is out of scope for the
# take-home. T12 verifies via `uv run` so this path is exercised end-to-end.
_EXAMPLE_PATH = Path(__file__).resolve().parent.parent.parent / "examples" / "inputs" / "full.json"


@app.command()
def value(
    input: Annotated[  # noqa: A002 — Typer convention
        Path,
        typer.Option(
            "--input",
            "-i",
            exists=True,
            readable=True,
            dir_okay=False,
            help="Path to a ValuationRequest JSON file.",
        ),
    ],
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            file_okay=False,
            help="Write report artifact(s) here instead of stdout.",
        ),
    ] = None,
    format: Annotated[  # noqa: A002 — Typer convention
        Format,
        typer.Option(
            "--format",
            "-f",
            case_sensitive=False,
            help="Output format. `both` writes/prints JSON and Markdown.",
        ),
    ] = Format.json,
) -> None:
    """Run triangulation on the request JSON at ``--input``."""
    try:
        request = ValuationRequest.model_validate_json(input.read_text(encoding="utf-8"))
    except ValueError as e:
        typer.echo(f"error: failed to parse request JSON: {e}", err=True)
        raise typer.Exit(code=2) from e

    triangulator = build_default_triangulator()
    try:
        valuation = triangulator.value(request)
    except (NoApplicableMethodError, ValueError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = _safe_stem(request.company.name)
        if format in (Format.json, Format.both):
            json_path = write_json(valuation, output_dir / f"{stem}.json")
            typer.echo(str(json_path))
        if format in (Format.markdown, Format.both):
            md_path = write_markdown(valuation, output_dir / f"{stem}.md")
            typer.echo(str(md_path))
        return

    if format is Format.markdown:
        typer.echo(to_markdown_str(valuation))
    elif format is Format.both:
        envelope = {
            "valuation": json.loads(to_json_str(valuation)),
            "markdown_report": to_markdown_str(valuation),
        }
        typer.echo(json.dumps(envelope, indent=2))
    else:
        typer.echo(to_json_str(valuation))


@app.command()
def methods() -> None:
    """List registered methods and their required inputs (JSON to stdout)."""
    descriptors = [d.model_dump() for d in default_method_descriptors()]
    typer.echo(json.dumps(descriptors, indent=2))


@app.command()
def example() -> None:
    """Print the bundled sample request (``examples/inputs/full.json``) to stdout."""
    if not _EXAMPLE_PATH.exists():
        typer.echo(
            f"error: bundled example not found at {_EXAMPLE_PATH}. "
            "Run from the project source tree.",
            err=True,
        )
        raise typer.Exit(code=2)
    sys.stdout.write(_EXAMPLE_PATH.read_text(encoding="utf-8"))


def _safe_stem(name: str) -> str:
    """Slugify a company name for filenames: lowercase, alnum/underscore only."""
    cleaned = "".join(c if c.isalnum() else "_" for c in name).strip("_").lower()
    return cleaned or "valuation"
