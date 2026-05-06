# VC Audit Tool — Implementation Plan

**Author:** Taylor Haaff
**Timeline:** 24–48h take-home
**Status:** Planning complete, ready to execute

---

## 1. Problem framing

Auditors reviewing VC portfolios need to estimate fair value of private, illiquid companies. Unlike public equities, there is no market price — auditors must derive a defensible estimate from sparse, non-standardized data. The deliverable is not a "correct" valuation; it is a **structured, auditable workflow** that produces consistent, well-documented estimates.

The grading rubric (per the prompt) emphasizes:

- Workflow translation, not financial modeling accuracy.
- Code quality, organization, documentation.
- Traceable, auditable derivation.
- Modularity and graceful error handling.

## 2. Chosen approach: multi-method triangulation

Rather than implement a single methodology, we implement three (**Comparable Company Analysis**, **Discounted Cash Flow**, **Last Round Market-Adjusted**) behind a common `ValuationMethod` interface, then orchestrate them with a **`Triangulator`** that:

1. Asks each method whether it is applicable given the inputs supplied.
2. Runs every applicable method.
3. Collects each method's `(point, low, high, confidence)` along with its assumptions and citations.
4. Synthesizes a final **point estimate** as a confidence-weighted average.
5. Reports a **range** as the min/max across methods (conservative, audit-friendly).
6. Reports a **dispersion metric** to flag model disagreement for reviewer attention.
7. Optionally accepts an auditor's **manual weight override** to encode professional judgment.

### Why this approach

ASC 820 (the U.S. GAAP fair-value-measurement standard) explicitly encourages cross-checking valuations using multiple techniques when reasonably available. Triangulation is therefore not a gimmick — it is *how the work is actually done*. It also:

- Demonstrates a clean strategy-pattern abstraction (vs. one monolithic method).
- Forces every method to declare its inputs, confidence, and provenance — which directly serves the "auditable" requirement.
- Produces a richer, more interesting walkthrough conversation.

## 3. Architecture

### 3.1 Layered architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Presentation                                                │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │  CLI (Typer)   │  │ FastAPI server │  │ Streamlit UI   │  │
│  │                │  │                │  │   (stretch)    │  │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘  │
│          │                   │                   │           │
└──────────┼───────────────────┼───────────────────┼───────────┘
           │                   │                   │
┌──────────▼───────────────────▼───────────────────▼───────────┐
│  Engine                                                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    Triangulator                        │  │
│  │  • discovers applicable methods                        │  │
│  │  • collects MethodResult[] in parallel                 │  │
│  │  • normalizes confidences → weights                    │  │
│  │  • applies manual weight overrides if supplied         │  │
│  │  • computes point (weighted avg), range (min/max),     │  │
│  │    dispersion ((high-low)/point)                       │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│  Methods (strategy pattern, ValuationMethod ABC)             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ CompsMethod  │  │ DCFMethod    │  │ LastRound    │        │
│  │              │  │              │  │ Method       │        │
│  └──────┬───────┘  └──────────────┘  └──────┬───────┘        │
└─────────┼─────────────────────────────────── ┼───────────────┘
          │                                    │
┌─────────▼────────────────────────────────────▼───────────────┐
│  Data providers (interface + mock impls)                     │
│  ┌──────────────────┐         ┌────────────────────────┐     │
│  │ CompsProvider    │         │ MarketIndexProvider    │     │
│  │ (mock universe)  │         │ (mock NASDAQ history)  │     │
│  └──────────────────┘         └────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  Output                                                      │
│  ┌────────────────────┐    ┌────────────────────────────┐    │
│  │ JSON report writer │    │ Markdown report writer     │    │
│  └────────────────────┘    └────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Request flow

```
ValuationRequest
      │
      ▼
┌──────────────┐
│ Triangulator │── for each registered method:
└──────┬───────┘     ├─ method.is_applicable(request)?
       │             └─ if yes, method.value(request) → MethodResult
       │
       │ MethodResult[]
       ▼
┌────────────────────────┐
│ Compute weights:       │
│  raw_confidence_i      │
│  / Σ raw_confidence    │
│ (or override if given) │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────────┐
│ Synthesize:                │
│  point  = Σ w_i × point_i  │
│  low    = min(low_i)       │
│  high   = max(high_i)      │
│  disp   = (high-low)/point │
└──────────┬─────────────────┘
           │
           ▼
TriangulatedValuation
           │
   ┌───────┴────────┐
   ▼                ▼
JSON report    Markdown report
```

### 3.3 Repository layout

```
modus-takehome/
├── pyproject.toml
├── README.md
├── PLAN.md                     ← this file
├── src/
│   └── vc_audit/
│       ├── __init__.py
│       ├── models/             ← Pydantic domain types
│       │   ├── __init__.py
│       │   ├── company.py
│       │   ├── request.py
│       │   ├── result.py
│       │   ├── citation.py
│       │   └── assumption.py
│       ├── methods/            ← strategy implementations
│       │   ├── __init__.py
│       │   ├── base.py         ← ValuationMethod ABC
│       │   ├── comps.py
│       │   ├── dcf.py
│       │   └── last_round.py
│       ├── data/               ← provider interfaces + mocks
│       │   ├── __init__.py
│       │   ├── comps_provider.py
│       │   ├── index_provider.py
│       │   └── fixtures/
│       │       ├── comp_universe.json
│       │       └── nasdaq_history.json
│       ├── engine/
│       │   ├── __init__.py
│       │   └── triangulator.py
│       ├── reports/
│       │   ├── __init__.py
│       │   ├── json_writer.py
│       │   └── markdown_writer.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── server.py       ← FastAPI app
│       ├── cli.py              ← Typer CLI entrypoint
│       └── ui/                 ← stretch: Streamlit
│           └── app.py
├── examples/
│   ├── inputs/                 ← sample request JSONs
│   └── outputs/                ← sample rendered reports
└── tests/
    ├── test_methods/
    ├── test_triangulator.py
    ├── test_reports.py
    ├── test_api.py
    └── test_cli.py
```

## 4. Domain model

All types are Pydantic v2. Monetary values are `Decimal`, never `float`.

```python
# models/company.py
class PortfolioCompany(BaseModel):
    name: str
    sector: str | None = None

# models/request.py
class FinancialProjection(BaseModel):
    year: int                      # offset from valuation date (1, 2, 3, ...)
    revenue: Decimal
    ebitda: Decimal
    capex: Decimal
    change_in_nwc: Decimal = Decimal(0)

class ValuationRequest(BaseModel):
    company: PortfolioCompany

    # Comps inputs
    revenue: Decimal | None = None
    ebitda: Decimal | None = None

    # Last Round inputs
    last_post_money_valuation: Decimal | None = None
    last_round_date: date | None = None
    reference_index: str = "NASDAQ"

    # DCF inputs
    projections: list[FinancialProjection] | None = None
    discount_rate: Decimal | None = None
    terminal_growth_rate: Decimal | None = None
    tax_rate: Decimal = Decimal("0.21")  # default US corporate rate; auditor-overridable

    # Auditor controls
    method_weights: dict[str, Decimal] | None = None  # name → weight
    as_of_date: date = Field(default_factory=date.today)

# models/citation.py
class Citation(BaseModel):
    source: str                    # e.g. "CompsProvider:mock_universe_v1"
    description: str
    retrieved_at: datetime
    url: str | None = None

# models/assumption.py
class Assumption(BaseModel):
    name: str                      # e.g. "EV/Revenue multiple"
    value: str                     # stringified for audit trail
    rationale: str

# models/result.py
class MethodResult(BaseModel):
    method_name: str
    point_estimate: Decimal
    low: Decimal
    high: Decimal
    confidence: Decimal            # raw [0,1], pre-normalization
    assumptions: list[Assumption]
    citations: list[Citation]
    notes: str | None = None

class MethodWeight(BaseModel):
    method_name: str
    raw_confidence: Decimal
    normalized_weight: Decimal     # sums to 1 across all methods
    overridden: bool = False

class TriangulatedValuation(BaseModel):
    company: PortfolioCompany
    as_of_date: date
    point_estimate: Decimal
    range_low: Decimal
    range_high: Decimal
    dispersion: Decimal            # (high-low)/point; flag > 0.5
    dispersion_flag: bool          # True if dispersion exceeds threshold
    method_results: list[MethodResult]
    weights: list[MethodWeight]
    request: ValuationRequest      # echoed for full audit trail
    generated_at: datetime
```

## 5. Component specifications

### 5.1 `ValuationMethod` ABC

```python
class ValuationMethod(ABC):
    name: ClassVar[str]

    @abstractmethod
    def is_applicable(self, request: ValuationRequest) -> bool: ...

    @abstractmethod
    def value(self, request: ValuationRequest) -> MethodResult: ...
```

Methods are stateless and side-effect-free. They receive the full request and return a complete `MethodResult` including their own confidence score.

### 5.2 `CompsMethod`

- **Applicable when:** `request.sector` is set AND (`revenue` or `ebitda`) is set.
- **Algorithm:**
  1. Pull comp universe via `CompsProvider`.
  2. Filter to same sector. Bail (low confidence) if fewer than 3 peers.
  3. Compute peer multiples: `EV / Revenue` and `EV / EBITDA` where available.
  4. Use the **median** multiple as the point estimate; **25th/75th percentile** for low/high.
  5. Apply: `point = median_multiple × target.revenue` (and analogous for EBITDA if available; if both, average them).
- **Confidence formula:**
  `min(1.0, n_peers / 8) × sector_match_factor`
  where `sector_match_factor` is 1.0 for exact match, 0.7 for adjacent (future enhancement; mock as 1.0 for now).
- **Citations:** `CompsProvider:<universe_id>`, list of peer tickers used.
- **Assumptions:** the median multiple, the peer set, which financial metric was used.

### 5.3 `LastRoundMethod`

- **Applicable when:** `last_post_money_valuation` AND `last_round_date` are set.
- **Algorithm:**
  1. Fetch index price at `last_round_date` and `as_of_date` from `MarketIndexProvider`.
  2. Compute `index_return = (price_now / price_then) − 1`.
  3. Apply: `point = last_post_money_valuation × (1 + index_return)`.
  4. Range: `point × [0.85, 1.15]` to reflect basis risk between a single index and a specific company.
- **Confidence formula:**
  `max(0, 1 − age_days / 730)` — full confidence at fresh round, zero at 2 years old.
- **Citations:** `MarketIndexProvider:NASDAQ`, the two specific price points used.
- **Assumptions:** chosen index, ±15% range factor, age decay formula.

### 5.4 `DCFMethod`

- **Applicable when:** `projections` (≥2 years), `discount_rate`, AND `terminal_growth_rate` are all supplied.
- **Algorithm:**
  1. Compute after-tax Free Cash Flow per projection year: `FCF = EBITDA × (1 − tax_rate) − capex − ΔNWC`. Default `tax_rate` is 0.21 (US corporate rate); auditor can override via the request field. This simplification does not separately model the depreciation tax shield because we don't carry D&A in the projection schema — slightly conservative (understates FCF).
  2. Discount each year's FCF at `discount_rate`.
  3. Compute terminal value via Gordon growth: `TV = FCF_final × (1 + g) / (r − g)`, discounted.
  4. Sum to get enterprise value.
  5. Range: `point × [0.80, 1.25]` to reflect projection uncertainty (Phase 3 upgrades this to a 3×3 sensitivity grid — see T15).
- **Confidence formula:**
  `min(1.0, projection_years / 5) × completeness_ratio`
  where `completeness_ratio` is the fraction of expected fields populated.
- **Citations:** the projection source (passed through from input).
- **Assumptions:** discount rate, terminal growth rate, tax rate (and whether default or overridden), FCF formula (no D&A tax shield modeled), ±range factor (or sensitivity grid bounds post-T15).

### 5.5 `Triangulator`

```python
class Triangulator:
    def __init__(self, methods: list[ValuationMethod]): ...

    def value(self, request: ValuationRequest) -> TriangulatedValuation:
        applicable = [m for m in self.methods if m.is_applicable(request)]
        if not applicable:
            raise NoApplicableMethodError(...)

        results = [m.value(request) for m in applicable]
        weights = self._compute_weights(results, request.method_weights)

        point = sum(w.normalized_weight * r.point_estimate
                    for w, r in zip(weights, results))
        low   = min(r.low  for r in results)
        high  = max(r.high for r in results)
        disp  = (high - low) / point if point else Decimal(0)

        return TriangulatedValuation(
            point_estimate=point,
            range_low=low,
            range_high=high,
            dispersion=disp,
            dispersion_flag=disp > Decimal("0.5"),
            ...
        )
```

**Weight computation:**

- If `method_weights` is supplied: validate keys match applicable methods, normalize to sum 1, mark `overridden=True`.
- Otherwise: normalize raw confidences. If all confidences are zero, fall back to equal weights and flag in notes.

### 5.6 Data providers

Both providers are interfaces with a mock implementation that reads from a JSON fixture. Real-API implementations could be swapped in via constructor injection without changing any other code.

```python
class CompsProvider(Protocol):
    def get_comps(self, sector: str) -> list[Comp]: ...

class MarketIndexProvider(Protocol):
    def get_price(self, index: str, on: date) -> Decimal: ...
```

**Mock data:**
- `comp_universe.json`: ~20 companies across sectors {SaaS, FinTech, Consumer, Healthcare, Industrials} with `ticker`, `sector`, `revenue`, `ebitda`, `enterprise_value`.
- `nasdaq_history.json`: monthly NASDAQ Composite levels for ~5 years.

### 5.7 Reports

- **JSON writer:** dumps the `TriangulatedValuation` as pretty-printed JSON with `Decimal` serialized to strings. This is the machine-readable audit artifact.
- **Markdown writer:** renders a structured report with sections:
  1. Header (company name, as-of date, generated timestamp)
  2. Headline result (point + range + dispersion flag)
  3. Per-method breakdown (each method's result, assumptions, citations, weight)
  4. Audit trail appendix (echoed request)

### 5.8 API

```
POST /valuations
  body: ValuationRequest (JSON)
  response: TriangulatedValuation (JSON) + markdown rendered separately at /valuations/{id}/report?format=md
GET  /health
GET  /methods         (lists registered methods and their input requirements)
```

FastAPI auto-generates OpenAPI docs at `/docs` — free demo asset.

### 5.9 CLI

```
vc-audit value --input path/to/request.json [--output-dir reports/] [--format json|md|both]
vc-audit methods                # list registered methods + their required inputs
vc-audit example                # write a sample request JSON to stdout
```

Both CLI and API call into the same `Triangulator` — the presentation layer is paper-thin.

## 6. Ticket map and parallelization

### 6.1 Ticket list

#### Phase 0 — Foundation (sequential, ~2 hr)

| ID | Title | Depends on | Est | Description |
|----|-------|------------|-----|-------------|
| T0 | Repo scaffold | — | 30m | `pyproject.toml`, ruff/black/pytest/mypy config, dir tree, README skeleton, Makefile |
| T1 | Domain models | T0 | 60m | All Pydantic types in §4. Tests for serialization round-trips. |
| T2 | `ValuationMethod` ABC + provider Protocols | T1 | 30m | Signatures only; no implementations. Locks the contract. |

#### Phase 1 — Parallel build

| ID | Title | Depends on | Est | Notes |
|----|-------|------------|-----|-------|
| T3a | `CompsProvider` mock + fixture | T1 | 45m | Hand-curated `comp_universe.json` |
| T3b | `MarketIndexProvider` mock + fixture | T1 | 45m | Hand-curated `nasdaq_history.json` |
| T4  | `CompsMethod` impl + unit tests | T2, T3a | 90m | |
| T5  | `LastRoundMethod` impl + unit tests | T2, T3b | 60m | |
| T6  | `DCFMethod` impl + unit tests | T2 | 90m | No external provider |
| T7  | `Triangulator` engine + unit tests | T2 | 75m | Test against fake methods, not real ones |
| T8  | JSON + Markdown report writers + tests | T1 | 60m | |
| T9  | Sample input fixtures (4 portfolio companies) | T1 | 30m | One per method shape + one with all data |

#### Phase 2 — Integration

| ID | Title | Depends on | Est | Notes |
|----|-------|------------|-----|-------|
| T10 | FastAPI app | T7, T8 | 60m | Endpoints from §5.8 |
| T11 | Typer CLI | T7, T8 | 45m | Commands from §5.9 |
| T12 | End-to-end integration tests | T9, T10, T11 | 60m | Real fixtures through CLI + API |

#### Phase 3 — Polish

| ID | Title | Depends on | Est | Notes |
|----|-------|------------|-----|-------|
| T15 | DCF sensitivity analysis upgrade | T6 | 75m | 3×3 grid: discount_rate ± 1pp × terminal_growth ± 0.5pp. Run DCFMethod 9 times with perturbed inputs; use min/max as range, midpoint as point. Replaces hardcoded ±20–25%. **Should land before T14** so example outputs reflect the upgrade. |
| T13 | README (problem, methodology, architecture, run, tradeoffs) | All | 60m | The sales pitch |
| T14 | Render example outputs into `examples/outputs/` | T11, T15 | 30m | Live artifacts to show |
| T16 | *(stretch)* Streamlit UI | T10 | 90m | Form → API → rendered MD report |
| T17 | *(stretch)* Per-method outlier detection in Triangulator | T7 | 45m | Flag any method whose point > 2× median or < 0.5× median across applicable methods. Add `outlier_method_names` to `TriangulatedValuation`; surface in markdown report. |

### 6.2 Dependency graph

```
T0
 │
 ▼
T1 ────────────────────────────────────────────────────────┐
 │                                                          │
 ▼                                                          │
T2 ─┬─► T3a ─► T4 ──┐                                       │
    │                │                                      │
    ├─► T3b ─► T5 ──┤                                       │
    │                ├──► T10 ──┐                           │
    ├──────► T6 ────┤            │                          │
    │                │            ├──► T12 ──► T13 ◄────────┤
    └──────► T7 ────┤            │                          │
                     │   ┌───────►├──► T14                  │
              T8 ────┤   │        │                         │
              T9 ────┴───┴► T11 ──┘                         │
                                                            │
                            T16 (stretch, after T10) ───────┤
                            T17 (stretch, after T7)  ───────┤
                            T15 (after T6, before T14) ─────┘
```

### 6.3 Suggested conductor parallelization

After T2 lands, fan out to three concurrent streams:

- **Agent A — Comps vertical:** T3a → T4 → tests
- **Agent B — Last Round vertical:** T3b → T5 → tests
- **Agent C — Core engine:** T6 + T7 + T8 (all interface-only deps; no need for real method impls to test the Triangulator)

Reconverge for Phase 2 with a single agent on T10 + T11 + T12 to keep API/CLI shape consistent. T13 (README) and T14 (example outputs) are last and parallelizable.

### 6.4 Total estimated effort

- **Phase 0:** 2 hr (sequential)
- **Phase 1:** ~9 hr serial / ~3.5 hr parallel (3 streams)
- **Phase 2:** ~2.75 hr (mostly serial)
- **Phase 3 core:** ~2.75 hr (T13 + T14 + T15)
- **Stretch (T16 Streamlit + T17 outliers):** +2.25 hr

**Realistic 48h budget usage: ~11–13 hr of focused work serial; ~7–8 hr with parallelization.** Leaves headroom for polish, debugging, and the stretch UI.

## 7. Decision log

These are the alternatives we considered and rejected. Useful for the walkthrough conversation.

### 7.1 Methodology: triangulation vs. single method

**Chose:** Triangulator with three methods (Comps + DCF + Last Round).

**Rejected:**
- *Single method (Comps only).* Would have been faster but limits demonstration of abstraction and produces a less interesting walkthrough. Also misses the chance to model real audit practice where cross-checking is encouraged by ASC 820.
- *Two methods (Comps + Last Round, drop DCF).* Considered because DCF is famously a poor fit for early-stage VC. Decided to keep DCF *because in a triangulation it adds an "intrinsic value" perspective independent of public markets*. Its low default confidence (when projections are short or noisy) means it self-deweights — this is itself an interesting design point.

### 7.2 Range synthesis: min/max vs. weighted envelope

**Chose:** min/max across methods, plus a separately reported dispersion metric.

**Rejected:**
- *Weighted envelope* (e.g., weighted average of low/high). Narrower range, more "math-y", but dishonestly hides model disagreement. Audit prefers conservatism in fair-value ranges.
- *Statistical confidence interval over a distribution of method outputs.* Overengineered for three data points; would invite questions about distributional assumptions we can't defend.

### 7.3 Auditor weight overrides: yes vs. no

**Chose:** Yes — `method_weights` is an optional field on `ValuationRequest`.

**Rejected:**
- *No override (data-driven only).* Cleaner but unrealistic. Real auditors apply judgment — sometimes a stale Last Round is still the best signal because the comp set is bad, and they need to encode that. Supporting overrides demonstrates domain awareness with low implementation cost.

### 7.4 Confidence scoring: derived vs. static

**Chose:** Derived from inputs (per-method formula).

**Rejected:**
- *Static weights* (e.g., Comps always 0.5, Last Round always 0.3). Simpler but unprincipled and indefensible in interview. Derived confidence lets the system respond to data quality (fresh round → high Last Round confidence; many peers → high Comps confidence).

### 7.5 Stack: Python vs. Node/TS

**Chose:** Python (FastAPI + Pydantic + Typer + Streamlit).

**Rejected:**
- *Node/TypeScript.* Type safety is comparable, but Python is the lingua franca for finance/data tooling and interviewers in this space will be more fluent. Pydantic specifically is unmatched for typed I/O models.

### 7.6 Interface: API + CLI + Streamlit vs. CLI only

**Chose:** API + CLI as core; Streamlit as stretch.

**Rejected:**
- *CLI only.* The prompt explicitly says "backend service" — leaning into HTTP demonstrates literal compliance. Also, candidate received feedback in a prior round that backend service depth was lacking.
- *Next.js / React frontend.* Time-prohibitive in 48h and would dilute backend focus. Streamlit gives a credible demo UI with ~90 minutes of work, all in Python.

### 7.7 Money type: `Decimal` vs. `float`

**Chose:** `Decimal` everywhere.

**Rejected:**
- *`float`.* Floating-point error in a financial audit tool is an immediate red flag. `Decimal` is the boring correct choice and shows attention to domain.

### 7.8 Data providers: real APIs vs. mocked fixtures

**Chose:** Mocked JSON fixtures behind interfaces (`Protocol` types).

**Rejected:**
- *Live Yahoo Finance / FRED / etc. integration.* Adds dependency risk, rate-limit hassle, and credentials management in a 48h take-home. The prompt explicitly endorses mocking. The interface boundary makes a real implementation a future drop-in.

### 7.9 DCF tax treatment

**Chose:** Compute FCF as `EBITDA × (1 − tax_rate) − capex − ΔNWC`. Default `tax_rate` = 0.21 (US corporate rate); auditor can override via the request field. Both the rate and whether it was defaulted vs. overridden are emitted as explicit Assumptions in the output.

**Rejected:**
- *No tax adjustment* (`FCF = EBITDA − capex − ΔNWC`). Simpler but overstates FCF by ~20% at typical tax rates. Defensible only because early-stage co's often have NOLs that shield taxes, but that's not universal — and "we ignored taxes" is the obvious first interview question. Adding the tax adjustment is ~15 minutes of work and preempts the question.
- *Full textbook unlevered FCF* (`FCF = EBIT × (1 − tax) + D&A − capex − ΔNWC`). Most accurate, but requires carrying D&A in the projection schema and modeling the depreciation tax shield. More inputs to defend, more places to be wrong, marginal accuracy gain for take-home purposes. Our chosen formula is a deliberate middle ground — taxes are present, but D&A complexity is not.

## 8. Non-goals

Explicitly out of scope. Calling these out prevents scope creep and is itself a useful interview talking point.

- Accurate financial modeling. The prompt says so directly.
- Peer-similarity scoring beyond exact sector match.
- Real-time market data integration.
- Authentication, multi-tenancy, or persistence (the API is stateless).
- A database. Inputs come from JSON; outputs are written as files or returned in the response.
- Currency conversion. All values assumed USD.
- Batch processing of multiple companies in one call (trivial extension if asked).

## 9. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Triangulator's weighted average can mask disagreement | Dispersion metric + flag surfaces this explicitly |
| Mocked comp universe feels handwavy | Use plausible real-ish numbers and cite "mocked" honestly in citations |
| DCF on early-stage co produces wild numbers | Low confidence by design self-deweights; document FCF simplification |
| Streamlit eats time and ships broken | Gate behind "core fully done" checkpoint; cut without regret if behind |
| Pydantic v1 vs. v2 confusion in test deps | Pin v2 in `pyproject.toml`; align all examples |
| Decimal serialization in JSON | Custom encoder (`str(d)`); document in README |

## 10. Stretch ideas (only if ahead of schedule)

- Streamlit UI (T15) — already in plan as gated stretch.
- A `/valuations/compare` endpoint that runs the same request through different weight scenarios.
- A "what-if" CLI flag that shows how the headline number moves as you bump each method's weight ±10%.
- Persisting reports with a content-addressed hash for true audit immutability.

## 11. Walkthrough talking points

What to emphasize in the 30-min interview:

1. **Why triangulation.** ASC 820 alignment. Real audit practice.
2. **The interface contract.** Show `ValuationMethod` ABC and explain how everything else falls out from it.
3. **Confidence as a first-class output.** Each method declares its own confidence from documented signals. The Triangulator does no magic.
4. **Min/max range + dispersion.** Conservative on purpose. Disagreement is surfaced, not smoothed away.
5. **Auditor override.** The model is a tool, not the decision-maker.
6. **Provenance.** Every output points back to its inputs, sources, and assumptions. The JSON report is the audit artifact.
7. **What we'd do next.** Real data providers, peer-similarity scoring, persistence, multi-currency, scenario analysis.
