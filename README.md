# VC Audit Tool

Auditable fair-value workflow for private VC portfolio companies. Runs three valuation methods (Comparable Companies, DCF, Last-Round Market-Adjusted) behind a common interface and **triangulates** them into a single point estimate, range, and dispersion metric. Every output is traceable back to its inputs, sources, and assumptions.

> Status: scaffolding (Phase 0). Methods, engine, and CLI/API land in subsequent phases per `PLAN.md`. T13 fleshes out this README.

## Approach

Multi-method triangulation behind a `ValuationMethod` strategy interface. Each method declares its own confidence; the `Triangulator` normalizes confidences to weights, computes a confidence-weighted point estimate, and reports min/max as the range plus a dispersion metric to flag model disagreement. ASC 820 paragraph 820-10-35-24A explicitly endorses this approach.

## Architecture

```
Presentation (CLI / FastAPI / Streamlit)
        │
   Engine (Triangulator)
        │
   Methods (Comps · DCF · LastRound) ── strategy pattern
        │
   Data providers (Comps universe · Market index)
        │
   Reports (JSON · Markdown)
```

See `PLAN.md` §3 for the full architecture diagram.

## Quickstart

```bash
make install        # uv sync
make check          # lint + format-check + typecheck + test
```

CLI and API entrypoints land in Phase 2 (T10/T11).

## Methods

| Method | Inputs | When confident |
|--------|--------|----------------|
| Comps  | sector, revenue (or EBITDA) | many sector peers |
| DCF    | projections, discount rate, terminal growth | long, complete projections |
| Last Round | last post-money valuation, round date | recent round |

## Tradeoffs & decisions

See `PLAN.md` §7 (decision log) and `discussion.md` (debrief notes).
