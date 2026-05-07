# VC Audit Tool

A structured, auditable fair-value workflow for private VC portfolio companies. The tool runs three valuation methods behind a single strategy interface, **triangulates** them into a point estimate plus a min/max range and dispersion metric, and emits an artifact (JSON + Markdown) that traces every number back to its inputs, sources, and assumptions. Designed against the ASC 820 Level 3 framing where multiple unobservable inputs must be reconciled into a single fair-value estimate; ASC 820-10-35-24A explicitly endorses combining methods rather than picking one.

## Methodology

| Method | Inputs | High-confidence when |
|---|---|---|
| **Comps** | sector, revenue (and/or EBITDA) | many sector peers; the company's metric is "covered" by the peer cluster |
| **DCF** | 1–5y projections, discount rate, terminal growth, tax rate | long horizon (≥3y), complete line items, `g < r` |
| **Last Round** | last post-money valuation, round date, market index | recent round (<12 months); confidence decays after that |

Each method emits a `MethodResult` with a point estimate, low/high range, confidence in [0, 1], and a list of citations + assumptions. The `Triangulator` normalizes confidences to weights, computes a confidence-weighted point estimate, takes elementwise min/max as the range, and flags dispersion `(high − low) / point > 0.5`. **Outlier detection** complements the aggregate flag: any method whose point estimate is >2× or <0.5× the median across applicable methods is named in the report headline (answers "*which* method disagrees?"). DCF reports its range using a 3×3 **sensitivity grid** over the two most consequential inputs (discount rate ± 1pp × terminal growth ± 0.5pp), with cells violating Gordon stability skipped and counted in the assumption rationale.

## Architecture

```
Presentation (CLI · FastAPI · Streamlit)
        │
   Engine (Triangulator + per-method weights)
        │
   Methods (Comps · DCF · LastRound)  ← strategy pattern, Protocol-based
        │
   Data providers (Comps universe · Market index)  ← Mock impls; drop-in real ones
        │
   Reports (JSON · Markdown)
```

See `PLAN.md` §3 for the full diagram with data-providers and reports broken out.

## Quickstart

```bash
make install                    # uv sync
make check                      # ruff + format-check + mypy --strict + pytest (158 tests)
make dev                        # FastAPI on :8000 — see /docs for OpenAPI
make ui                         # Streamlit demo on :8501 (uv sync --extra ui first)
make examples                   # regenerate examples/outputs/ from examples/inputs/
```

## Using the tool

**CLI** — one command per format, or `both` to write into a directory:

```bash
uv run vc-audit example | uv run vc-audit value -i /dev/stdin --format markdown
uv run vc-audit value -i examples/inputs/full.json --format both -o examples/outputs/
```

**API** — `POST /valuations` with a `ValuationRequest` JSON body; supports `?format=json|markdown|both`. `/methods` lists registered methods and their applicability rules; `/health` is a 200 ok. Live OpenAPI at `localhost:8000/docs`.

**UI** — `make ui` opens a Streamlit page with three input modes (load a bundled fixture, fill out a structured form, or paste JSON). The page wires `build_default_triangulator()` in-process and renders the markdown report and raw JSON side-by-side.

Canonical demo pair: [`examples/inputs/full.json`](examples/inputs/full.json) → [`examples/outputs/full.md`](examples/outputs/full.md).

## Key design decisions and tradeoffs

- **Triangulation over single-method**: ASC 820 endorses it, and the dispersion metric flags exactly the cases where the auditor's judgment matters most. Picking the "best" method per company would surface less actionable disagreement.
- **Confidence is a first-class output**, computed per-method (e.g., DCF's confidence scales with horizon coverage × completeness; Last Round's decays exponentially with round age). Auditors see *why* a method is weighted heavily, not a static priority list.
- **Range = elementwise min/max, not a confidence-weighted envelope.** The weighted envelope hides the worst-case spread. Min/max + dispersion answers "what's the widest the methods disagree?" — auditors care about that distance, not a smoothed band.
- **Outlier detection complements `dispersion_flag`** — the flag answers "is there disagreement?", the named methods answer "which method is the outlier?". Two lines of headline cost; both are decision-relevant.
- **DCF range from a 3×3 sensitivity grid**, not a hardcoded ±N% factor. The grid reflects sensitivity to the two most consequential inputs; the ±N% placeholder told a confident-looking story disconnected from the actual model.
- **`Decimal` everywhere** for money and rates. No float arithmetic touches a valuation number.
- **Providers behind a `Protocol`**: `MockCompsProvider` and `MockMarketIndexProvider` ship with the repo. A real implementation drops into `build_default_triangulator()` without engine changes.
- **Auditor weight overrides** (`request.method_weights`) are first-class. Auditor judgment isn't an afterthought — it's a typed, validated input echoed in the audit trail.

## What I'd do next with more time

- Real provider integrations (Yahoo Finance / FRED / a peer-comp data source) replacing the mocks.
- Per-sector calibration of the dispersion threshold (currently a global 0.5 heuristic).
- Content-addressed report store: hash the request + engine version → cache-immutable JSON output.
- Peer-similarity scoring beyond exact-sector match (size buckets, growth-stage tags, geography).
- Run history + scenario diffing: "what changed between the Q3 and Q4 valuations of this company?".
- Property-based tests for the triangulator's invariants (range_low ≤ point ≤ range_high; weights sum to 1.0).

## Repo layout

```
src/vc_audit/        engine, methods, data providers, reports, CLI, API, UI
  ├── engine/        Triangulator + factory
  ├── methods/       CompsMethod, DCFMethod, LastRoundMethod (+ Protocol)
  ├── data/          Mock providers behind Protocols
  ├── reports/       JSON + Markdown writers
  ├── api/           FastAPI server
  ├── cli.py         Typer CLI entry point
  └── ui/            Streamlit page (optional, gated by [project.optional-dependencies] ui)
tests/               158 tests covering every module
examples/inputs/     6 bundled fixtures (full, dcf-only, comps-only, last-round-only,
                     high-dispersion, with-overrides)
examples/outputs/    Rendered .json + .md per fixture (regenerable via `make examples`)
PLAN.md              Phase-by-phase plan; §3 has the full architecture diagram
discussion.md        Per-decision design notes (the "why" behind each tradeoff)
```
