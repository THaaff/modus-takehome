"""Typer CLI entrypoint. Filled in by T11; placeholder so [project.scripts] resolves."""

import typer

app = typer.Typer(help="VC Audit Tool — fair-value triangulation for private portfolio companies.")


@app.callback()
def _root() -> None:
    """Root command. Subcommands land in T11 (value, methods, example)."""
