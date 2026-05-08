"""FastAPI app: stateless HTTP surface over the triangulation engine.

Three endpoints:
- ``GET /health`` — liveness check, returns ``{"status": "ok"}``.
- ``GET /methods`` — auditor-facing metadata (one descriptor per registered method).
- ``POST /valuations`` — runs triangulation. The ``format`` query param controls both
  the response Content-Type and the body shape:

  * ``json``     → ``application/json`` body is the ``TriangulatedValuation``
  * ``markdown`` → ``text/markdown`` body is the rendered report
  * ``both``     → ``application/json`` envelope ``{valuation, markdown_report}``

Every output is reproducible from the request alone — no IDs, no persistence. The
Triangulator instance is cached at module import time via ``functools.lru_cache`` so
warm requests skip provider re-instantiation.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from vc_audit import __version__
from vc_audit.engine import (
    Triangulator,
    build_default_triangulator,
    default_method_descriptors,
)
from vc_audit.methods import MethodDescriptor, NoApplicableMethodError
from vc_audit.models import ValuationRequest
from vc_audit.reports import to_markdown_str


class ReportFormat(StrEnum):
    """Mirror of the CLI ``--format`` flag."""

    json = "json"
    markdown = "markdown"
    both = "both"


@lru_cache(maxsize=1)
def _triangulator() -> Triangulator:
    """Cached default engine; tests can clear via ``_triangulator.cache_clear()``."""
    return build_default_triangulator()


app = FastAPI(
    title="VC Audit Tool",
    version=__version__,
    description=(
        "Stateless multi-method fair-value triangulation for private VC portfolio "
        "companies. Every response is reproducible from the request body alone."
    ),
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/methods", response_model=list[MethodDescriptor])
def methods() -> list[MethodDescriptor]:
    """List registered valuation methods and their required inputs."""
    return default_method_descriptors()


@app.post("/valuations")
def valuations(
    request: ValuationRequest,
    format: ReportFormat = ReportFormat.json,
) -> Response:
    """Run triangulation and return the result in the requested format."""
    try:
        valuation = _triangulator().value(request)
    except NoApplicableMethodError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    if format is ReportFormat.markdown:
        return PlainTextResponse(to_markdown_str(valuation), media_type="text/markdown")
    if format is ReportFormat.both:
        envelope: dict[str, Any] = {
            "valuation": valuation.model_dump(mode="json"),
            "markdown_report": to_markdown_str(valuation),
        }
        return JSONResponse(envelope)
    # Default: JSON. Use model_dump(mode="json") so DecimalStr serializes to strings.
    return JSONResponse(valuation.model_dump(mode="json"))
