# VC Audit Tool

**Thesis:** I decided that instead of focusing on a single valuation method, it would be better (and more indicative of real-world auditor behavior) to combine the outputs of a few different valuation methods (Comparable Company Analysis, Discounted Cash Flow, Last Round Market-Adjusted) into a single point estimate. The system takes guidance from [ASC 820 Level 3 fair-value measurement][asc820-l3], which **explicitly endorses combining methods rather than picking one.** The strategy is to gather the results of these valuation methods based on the provided data, and triangulate them into a confidence-weighted point, a range, a flag to indicate that the valuation could use more investigation, as well as per-method outlier detection. The final output from the CLI or web UI can be a JSON or Markdown object which traces every number back to its inputs, sources, and assumptions.

**See [`PLAN.md`](PLAN.md) for the full architecture diagram, request flow, component specs, and decision log.**

## What the engine does

The `Triangulator`:
- asks each method `is_applicable(request)` so missing inputs don't kill the run,
- normalizes per-method confidence into weights,
- computes `point = Σ wᵢ × pointᵢ`, `range = (min(lowᵢ), max(highᵢ))`,
- flags `dispersion = (high − low) / point > 0.5`,
- names the **outlier** method (>2× or <0.5× the median across applicable methods),
- accepts `request.method_weights` so auditor judgment is a typed, validated input — not a footnote.

Confidence is per-method, derived from the data: DCF scales with horizon coverage × completeness; Last Round decays exponentially with round age (zero at 2 years); Comps scales with peer count.

## The three methods

| Method | Inputs | High-confidence when |
|---|---|---|
| **Comps** | sector, revenue (and/or EBITDA) | many sector peers; the company's metric is "covered" by the peer cluster |
| **DCF** | 1–5y projections, discount rate, terminal growth, tax rate | long horizon (≥3y), complete line items, `g < r` |
| **Last Round** | last post-money valuation, round date, market index | recent round (<12 months); confidence decays after that |

## Quickstart
```bash
make install                    # uv sync
make check                      # ruff + format-check + mypy --strict + pytest (176 tests)
make dev                        # FastAPI on :8000 — see /docs for OpenAPI
make ui                         # Streamlit demo on :8501 (uv sync --extra ui first)
make examples                   # regenerate examples/outputs/ from examples/inputs/
```

**Where to start as a reviewer:** open [`examples/outputs/full.md`](examples/outputs/full.md) for what the tool produces, then [`src/vc_audit/engine/triangulator.py`](src/vc_audit/engine/triangulator.py) for how.

## Using the tool

**CLI** — one command per format, or `both` to write into a directory:

```bash
uv run vc-audit example | uv run vc-audit value -i /dev/stdin --format markdown
uv run vc-audit value -i examples/inputs/full.json --format both -o examples/outputs/
```

**API** — `POST /valuations` with a `ValuationRequest` JSON body; supports `?format=json|markdown|both`. `/methods` lists registered methods and applicability rules. Live OpenAPI at `localhost:8000/docs`.

**UI** — `make ui` opens a Streamlit page with three input modes (load a bundled fixture, fill a structured form, or paste JSON). Renders the markdown report and raw JSON side-by-side.

## Key design decisions

Triangulation over single-method (ASC 820 grounding); `Decimal` everywhere for money and rates; providers behind a `Protocol` so mock/real implementations swap without engine changes; range as elementwise min/max for honest worst-case spread; per-method outlier detection complementing the dispersion flag; DCF range from a 3×3 sensitivity grid rather than a hardcoded ±N% factor; auditor weight overrides as a first-class typed input.

See [`PLAN.md`](PLAN.md) §6 for the full decision log including alternatives considered and rejected.

## What I'd do next

- Real provider integrations (Yahoo Finance / FRED / a peer-comp source) replacing the mocks.
- **Calibration check** (ASC 820 concept): given a recent observable transaction, recalibrate model multiples to match — quantifies method bias.
- **OPM Backsolve** as a fourth method for capital-structure-aware allocation across share classes.
- Per-sector calibration of the dispersion threshold (currently a global 0.5 heuristic).
- Content-addressed report store: hash request + engine version → cache-immutable output.
- Property-based tests for triangulator invariants (`range_low ≤ point ≤ range_high`; weights sum to 1.0).

## Sources

- [ASC 820-10-35-24B][asc820-24b] — endorses use of multiple valuation techniques when no quoted price exists in an active market, and requires the entity to weigh their results.
- [ASC 820 fair-value hierarchy (Level 1/2/3)][asc820-l3] — private portfolio companies fall under Level 3 (unobservable inputs).
- [IPEV Valuation Guidelines (Dec 2025)][ipev] — global VC/PE-specific standard, aligned with ASC 820 and IFRS 13.
- US 21% corporate tax rate (default in `ValuationRequest.tax_rate`): [Internal Revenue Code §11][irc-11].

[asc820-l3]: https://viewpoint.pwc.com/dt/us/en/pwc/accounting_guides/fair_value_measureme/fair_value_measureme__9_US/chapter_1_introducti__1_US/15_key_concepts_in_a_US.html
[asc820-24b]: https://dart.deloitte.com/USDART/home/codification/broad-transactions/asc820-10/roadmap-fair-value-measurements-disclosures/chapter-10-subsequent-measurement/10-3-valuation-techniques
[ipev]: https://www.privateequityvaluation.com/Portals/0/Documents/Guidelines/2025%20IPEV%20Valuation%20Guidelines.pdf
[irc-11]: https://www.law.cornell.edu/uscode/text/26/11
