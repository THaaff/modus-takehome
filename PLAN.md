# VC Audit Tool — Design

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

## 3. Architecture

### 3.1 Layered architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Presentation                                                │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │  CLI (Typer)   │  │ FastAPI server │  │ Streamlit UI   │  │
│  │                │  │                │  │                │  │
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
vc-audit/
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
│       └── ui/                 ← Streamlit demo
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
  5. Range: a 3×3 sensitivity grid over discount_rate ± 1pp × terminal_growth ± 0.5pp. Min/max of the valid cells defines the range; midpoint defines the point. Cells violating Gordon stability (g ≥ r) are skipped and counted in the assumption rationale.
- **Confidence formula:**
  `min(1.0, projection_years / 5) × completeness_ratio`
  where `completeness_ratio` is the fraction of expected fields populated.
- **Citations:** the projection source (passed through from input).
- **Assumptions:** discount rate, terminal growth rate, tax rate (and whether default or overridden), FCF formula (no D&A tax shield modeled), sensitivity grid bounds and any skipped cells.

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

## 6. Decision log

These are the alternatives we considered and rejected.

### 6.1 Methodology: triangulation vs. single method

**Chose:** Triangulator with three methods (Comps + DCF + Last Round).

**Rejected:**
- *Single method (Comps only).* Faster to build but limits demonstration of the strategy abstraction and misses the chance to model real audit practice, where cross-checking is encouraged by ASC 820.
- *Two methods (Comps + Last Round, drop DCF).* Considered because DCF is famously a poor fit for early-stage VC. Decided to keep DCF *because in a triangulation it adds an "intrinsic value" perspective independent of public markets*. Its low default confidence (when projections are short or noisy) means it self-deweights — this is itself an interesting design point.

### 6.2 Range synthesis: min/max vs. weighted envelope

**Chose:** min/max across methods, plus a separately reported dispersion metric.

**Rejected:**
- *Weighted envelope* (e.g., weighted average of low/high). Narrower range, more "math-y", but dishonestly hides model disagreement. Audit prefers conservatism in fair-value ranges.
- *Statistical confidence interval over a distribution of method outputs.* Overengineered for three data points; would invite questions about distributional assumptions we can't defend.

### 6.3 Auditor weight overrides: yes vs. no

**Chose:** Yes — `method_weights` is an optional field on `ValuationRequest`.

**Rejected:**
- *No override (data-driven only).* Cleaner but unrealistic. Real auditors apply judgment — sometimes a stale Last Round is still the best signal because the comp set is bad, and they need to encode that. Supporting overrides demonstrates domain awareness with low implementation cost.

### 6.4 Confidence scoring: derived vs. static

**Chose:** Derived from inputs (per-method formula).

**Rejected:**
- *Static weights* (e.g., Comps always 0.5, Last Round always 0.3). Simpler but unprincipled. Derived confidence lets the system respond to data quality (fresh round → high Last Round confidence; many peers → high Comps confidence).

### 6.5 Stack: Python vs. Node/TS

**Chose:** Python (FastAPI + Pydantic + Typer + Streamlit).

**Rejected:**
- *Node/TypeScript.* Type safety is comparable, but Python is the lingua franca for finance/data tooling. Pydantic specifically is unmatched for typed I/O models.

### 6.6 Interface: API + CLI + Streamlit vs. CLI only

**Chose:** API + CLI as core; Streamlit as the demo surface.

**Rejected:**
- *CLI only.* Leaning into HTTP demonstrates the "backend service" framing and gives reviewers an OpenAPI surface to inspect.
- *Next.js / React frontend.* Time-prohibitive given the build window and would dilute backend focus. Streamlit gives a credible demo UI in pure Python.

### 6.7 Money type: `Decimal` vs. `float`

**Chose:** `Decimal` everywhere.

**Rejected:**
- *`float`.* Floating-point error in a financial audit tool is an immediate red flag. `Decimal` is the boring correct choice and shows attention to domain.

### 6.8 Data providers: real APIs vs. mocked fixtures

**Chose:** Mocked JSON fixtures behind interfaces (`Protocol` types).

**Rejected:**
- *Live Yahoo Finance / FRED / etc. integration.* Adds dependency risk, rate-limit hassle, and credentials management. The interface boundary makes a real implementation a future drop-in.

### 6.9 DCF tax treatment

**Chose:** Compute FCF as `EBITDA × (1 − tax_rate) − capex − ΔNWC`. Default `tax_rate` = 0.21 (US corporate rate); auditor can override via the request field. Both the rate and whether it was defaulted vs. overridden are emitted as explicit Assumptions in the output.

**Rejected:**
- *No tax adjustment* (`FCF = EBITDA − capex − ΔNWC`). Simpler but overstates FCF by ~20% at typical tax rates. Defensible only because early-stage co's often have NOLs that shield taxes, but that's not universal — and "we ignored taxes" is the obvious first question to ask of any DCF. Adding the tax adjustment is cheap and preempts it.
- *Full textbook unlevered FCF* (`FCF = EBIT × (1 − tax) + D&A − capex − ΔNWC`). Most accurate, but requires carrying D&A in the projection schema and modeling the depreciation tax shield. More inputs to defend, more places to be wrong, marginal accuracy gain at this scope. Our chosen formula is a deliberate middle ground — taxes are present, but D&A complexity is not.

## 7. Non-goals

Explicitly out of scope.

- Accurate financial modeling. The prompt says so directly.
- Peer-similarity scoring beyond exact sector match.
- Real-time market data integration.
- Authentication, multi-tenancy, or persistence (the API is stateless).
- A database. Inputs come from JSON; outputs are written as files or returned in the response.
- Currency conversion. All values assumed USD.
- Batch processing of multiple companies in one call (trivial extension if asked).

## 8. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Triangulator's weighted average can mask disagreement | Dispersion metric + flag surfaces this explicitly |
| Mocked comp universe feels handwavy | Use plausible real-ish numbers and cite "mocked" honestly in citations |
| DCF on early-stage co produces wild numbers | Low confidence by design self-deweights; document FCF simplification |
| Streamlit eats time and ships broken | Gate behind "core fully done" checkpoint; cut without regret if behind |
| Pydantic v1 vs. v2 confusion in test deps | Pin v2 in `pyproject.toml`; align all examples |
| Decimal serialization in JSON | Custom encoder (`str(d)`); document in README |

## 9. Future enhancements

- A `/valuations/compare` endpoint that runs the same request through different weight scenarios.
- A "what-if" CLI flag that shows how the headline number moves as you bump each method's weight ±10%.
- Persisting reports with a content-addressed hash for true audit immutability.

