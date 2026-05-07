# Discussion & Study Notes — VC Audit Tool

Living document. Add notes here as we work. Sections are independent — read in any order.

---

## 1. Glossary

The vocabulary you'll need to recognize and use in the walkthrough. Where useful, I've drawn parallels to public-equity / stock-trading concepts you already know.

### Audit & accounting

- **Fair value** — the price you'd realistically get if you sold the asset today in an orderly transaction between willing parties. The whole point of this exercise is *estimating* fair value when there's no market price.
- **ASC 820** — the U.S. accounting standard (under US GAAP) that defines fair value and how to measure it. Its **fair value hierarchy** has three levels:
  - **Level 1:** quoted prices in active markets (e.g., AAPL stock). Trivial.
  - **Level 2:** observable inputs other than quoted prices (e.g., similar assets that *do* trade). Harder.
  - **Level 3:** unobservable inputs — model-based estimates. **Private VC portfolio companies are Level 3.** This is what our tool helps with.
- **Mark / marking** — assigning a current value to a position. "Marking to market" = using a market price; "marking to model" = using a calculation. Public stocks are marked to market; VC is marked to model. Auditors check the marks.
- **409A valuation** — a related but distinct exercise: an IRS-required valuation of a private company's *common stock* used for setting employee option strike prices. Different purpose, same general toolkit. Mention if asked but don't conflate.

### VC mechanics

- **Portfolio company** — a private company that a VC fund owns equity in.
- **Round** — a financing event (Series A, B, C, etc.). Each round sets a new valuation.
- **Pre-money / post-money valuation** — pre-money = the value of the company *before* new investment; post-money = pre-money + new cash raised. If a $20M Series A goes in at $80M pre-money, post-money is $100M and the new investors own 20%.
- **Down round** — a financing where the new valuation is *below* the prior round's valuation. Painful for everyone, often triggers anti-dilution clauses. Relevant to Last Round method: a fresh down round overrides everything.
- **Dry powder** — committed but un-invested fund capital. Not directly relevant to this tool but you'll hear it.

### Financial-modeling

- **Enterprise Value (EV)** — value of the *whole business*, regardless of how it's financed. Roughly: market cap + debt − cash. Useful because it's capital-structure-agnostic, so you can compare a debt-heavy company to a debt-free one.
- **EBITDA** — Earnings Before Interest, Taxes, Depreciation, Amortization. A rough proxy for operating cash generation. Strips out financing decisions (interest), tax regimes (taxes), and accounting allocations (D&A). Loved by bankers, distrusted by Buffett ("does management think the tooth fairy pays for capex?").
- **EBIT** — Earnings Before Interest and Taxes. EBITDA minus D&A. Closer to "real" operating profit because D&A is a real cost (assets wear out).
- **NOPAT** — Net Operating Profit After Tax = EBIT × (1 − tax rate). The standard "what does the business actually earn after taxes, ignoring how it's financed" number.
- **FCF (Free Cash Flow)** — cash a business actually produces after funding itself. The thing you discount in a DCF. Standard textbook formula:
  ```
  FCF = EBIT × (1 − tax_rate) + D&A − capex − ΔNWC
  ```
- **Capex** — Capital Expenditures. Cash spent on long-lived assets. Real outflow even though accounting spreads it across years via depreciation.
- **ΔNWC** — Change in Net Working Capital = change in (current assets − current liabilities). Growing companies absorb cash here (you fund customers' payment terms before collecting). Real cash effect.
- **NOL** — Net Operating Loss. Past losses you can use to shield future taxable income. Early-stage companies usually have a stack of these — relevant to why "no tax" in DCF isn't crazy for early VC.
- **Multiple** — a ratio applied to a financial metric to imply value. `EV / Revenue = 8x` means "businesses like this typically trade at 8x their revenue." Stock traders use P/E (price-to-earnings) the same way.
- **Discount rate** — the interest rate used to convert future dollars to present dollars. $100 in 1 year at a 10% discount rate is worth $90.91 today. Higher discount rate = future cash is worth less today = lower valuation.
- **WACC** — Weighted Average Cost of Capital. The standard discount rate used in corporate DCF. Blends cost of debt and cost of equity by their weights in the capital structure. We don't compute it from scratch — we accept it as an input.
- **Terminal value** — in a DCF, you can't project forever, so after the explicit forecast period you assume the company keeps growing at a steady rate forever. Terminal value captures the present value of all that.
- **Gordon growth formula** — the standard way to compute terminal value:
  ```
  TV = FCF_final × (1 + g) / (r − g)
  ```
  where `g` is the perpetual growth rate and `r` is the discount rate. Sensitive to both inputs — small changes move the result a lot.
- **Comparable companies (comps)** — public companies similar enough to your private target that you can borrow their valuation multiples.

### Risk & statistics terms

- **Basis risk** — when you hedge or proxy with one instrument but the thing you actually care about behaves differently. NASDAQ vs. a single SaaS startup is a textbook example. Familiar from futures trading.
- **Dispersion** — how spread out a set of numbers is. We use it as a "do the methods agree?" signal.
- **Sensitivity analysis** — re-running a model with different inputs to see how much the output moves. Standard finance practice for any DCF.

---

## 2. Why valuing private companies is hard (1-paragraph framing)

Public stocks have a price. Private companies don't. Auditors still need a defensible number for fund NAV reporting. They have to construct that number from sparse, non-standardized inputs (internal financials of varying quality, the last funding round, public comps that don't quite match) using a method they can defend in writing. The challenge is less "compute the right number" and more "produce a process that's repeatable, traceable, and explainable" — which is exactly what our tool models.

---

## 3. Why triangulation (the core design choice)

ASC 820 explicitly encourages cross-checking valuations using multiple techniques when reasonably available. In practice, audit teams almost always look at multiple methods and reconcile them — they don't pick one and live with it.

So instead of implementing a single method (which would be 90% boilerplate, 10% interesting), we:

1. Implement three methods behind a common interface.
2. Run all of them whenever the data supports it.
3. Synthesize a final estimate that explicitly weights each by its data quality.
4. Surface disagreement (the dispersion metric) instead of smoothing it away.

**Why this is the right choice for the take-home specifically:**

- Aligns with real audit practice → the interviewer should immediately recognize it.
- Demonstrates a clean abstraction (strategy pattern) — much stronger code-design talking point than a single method would give us.
- Makes the *system design* the interesting story, not the math of any one method (which the prompt explicitly says is not what's being graded).

---

## 4. The three methods — concept and when each fits

### Comparable Company Analysis (Comps)

- **Idea:** find public companies similar to your target, look at how the market values them per dollar of revenue (or EBITDA), and apply that ratio to your target's revenue.
- **Math:**
  ```
  median_multiple = median(EV_i / Revenue_i  for i in peers)
  fair_value      = median_multiple × target_revenue
  ```
- **Best when:** target has revenue, sector has good public comps (e.g., SaaS — tons of public SaaS companies; vertical software for dental clinics — almost none).
- **Weakness:** "comparable" is doing a lot of work. A pre-revenue startup vs. mature public company aren't really comparable even in the same sector.

### Discounted Cash Flow (DCF)

- **Idea:** project the company's future cash flows, discount them back to today, sum them up.
- **Math:**
  ```
  enterprise_value = Σ [ FCF_t / (1 + r)^t ]  for t in 1..N
                   + terminal_value / (1 + r)^N
  ```
- **Best when:** you have credible multi-year projections and the business has predictable cash generation.
- **Weakness for VC:** early-stage companies don't have predictable cash flows, and projections are aspirational. DCF on a Series A startup is mostly fiction. We include it anyway because *in a triangulation* it adds an "intrinsic value" perspective independent of the public market — and its low confidence (driven by short/sparse projections) means it self-deweights when the inputs are weak.

### Last Round (Market-Adjusted)

- **Idea:** start from the company's last funding-round valuation, then adjust for how a public market index has moved since then.
- **Math:**
  ```
  index_return = price_now / price_at_round − 1
  fair_value   = last_post_money_valuation × (1 + index_return)
  ```
- **Best when:** the round is recent (< 1 year) and the company is in a sector tracked by your reference index.
- **Weakness:** assumes the company moves with the index, which is rough. A fresh round dominates this method's confidence; an old round destroys it.

---

## 5. The three open design decisions (study these)

These were the decisions we walked through. Be ready to defend in the interview.

### 5a. DCF tax treatment

**The textbook FCF formula:**
```
FCF = EBIT × (1 − tax_rate) + D&A − capex − ΔNWC
```

**Our chosen formula:**
```
FCF = EBITDA × (1 − tax_rate) − capex − ΔNWC      [tax_rate defaults to 0.21]
```

The `tax_rate` is an auditor-overridable field on the request, defaulting to the US corporate rate (21%). Both the rate value and whether it was defaulted vs. overridden are emitted as named Assumptions in the output.

**Why this formula and not the textbook version:** the textbook formula needs D&A as a separate field so you can apply tax to the EBIT base and then add back D&A as a non-cash item (the "depreciation tax shield"). Our `FinancialProjection` schema only carries EBITDA — adding D&A means more input to defend and more to be wrong about. Applying tax directly to EBITDA is slightly conservative (understates FCF by the missing tax shield), which is the right direction for audit work.

**Defense in interview:**
- "Tax is an input with a defensible default (US corporate rate), and the audit trail records whether the auditor accepted the default or overrode it."
- "We don't model the depreciation tax shield because we don't carry D&A in the projection schema. The result is slightly conservative, which I'd argue is the right bias for fair-value work."
- "The full textbook treatment is a future enhancement that would require expanding the projection schema."

**Alternatives considered and rejected:**

| Alternative | Why rejected |
|---|---|
| **No tax adjustment** (`FCF = EBITDA − capex − ΔNWC`). The original simplification. | Overstates FCF by ~20% at typical tax rates. The obvious first interview question would be "but what about taxes?" Adding the tax field preempts that for ~15 min of work. |
| **Full textbook unlevered FCF** with D&A modeled separately. | Most accurate. Requires carrying D&A in the projection schema, defending a separate D&A schedule, and modeling the tax shield. Marginal accuracy gain for take-home purposes; more places to be wrong. |
| **Effective tax rate per company** (rather than a flat default). | Most realistic — early-stage co's with NOLs really do have ~0% effective tax for years. But "what's the right effective rate" is its own rabbit hole. The override field handles this case for any auditor who wants to set it explicitly. |

### 5b. Range factors (±15%, ±20–25%)

**What they mean:**

- Last Round ±15% = "we used a public index as a proxy; the proxy doesn't track this specific company perfectly." This is **basis risk**.
- DCF ±20–25% = "DCFs are notoriously sensitive — moving the discount rate 1 percentage point can shift the answer 15–20%."

**Defense in interview:**
- "Last Round's ±15% is a hardcoded basis-risk haircut. I called it out as an explicit Assumption in the output so it's auditable, but it's a heuristic — a real implementation might calibrate it from sector-level historical volatility."
- "DCF originally used the same hardcoded approach but I upgraded it post-Phase 2 to a real **3×3 sensitivity grid** (T15): re-run the DCF with discount_rate ± 1pp × terminal_growth ± 0.5pp and use the min/max of the resulting nine valuations as the range. That's a much more defensible derivation of uncertainty."
- "The same upgrade for Last Round would require historical volatility data per sector — out of scope for the take-home but a clear next step."

**Resolved as T15** (Phase 3, planned post-Phase 2). DCF will land with hardcoded ±20–25% during Phase 1 then get upgraded to the sensitivity grid before example outputs are rendered (so the demo artifacts show the better version).

### 5c. Dispersion threshold (0.5)

**The metric:**
```
dispersion = (range_high − range_low) / point_estimate
```

Worked example: point = $100M, low = $80M, high = $130M → dispersion = 0.50 → flag triggers.

**Why a flag matters:** if methods disagree wildly, the weighted-average point estimate hides that disagreement. The flag forces a human to look at the per-method breakdown.

**Threshold tradeoff:**

| Threshold | Behavior |
|---|---|
| 0.2 | Flags everything → alarm fatigue |
| 0.5 (chosen) | Flags genuinely large disagreements |
| 1.0 | Flags only catastrophic mismatches → too late |

**Defense in interview:** "0.5 is a heuristic. In a real product you'd calibrate it from historical review data — at what dispersion level do reviewers actually overrule the model? Without that data, 0.5 is a defensible 'large but not extreme' threshold."

**Complementary stretch (T17):** **per-method outlier detection.** Dispersion is a single aggregate signal — it tells you "the methods disagree" but not "this specific method is the disagreement." T17 adds: flag any individual method whose point estimate is > 2× the median or < 0.5× the median across applicable methods. The output names the outlier method explicitly, which is more actionable for the reviewer. We chose to keep the dispersion flag *and* add per-method outliers as a stretch (rather than replacing one with the other) because they answer different questions: "is there disagreement?" vs. "where is the disagreement coming from?"

---

## 6. Audit-domain concepts to internalize

These are concepts the interviewer might assume you know.

### The fair-value hierarchy (ASC 820)

- **Level 1** (quoted prices, active market) — easy.
- **Level 2** (observable inputs, similar assets trading) — moderate.
- **Level 3** (unobservable, model-based) — what our tool addresses. Subject to the most audit scrutiny because there's the most discretion.

If asked "where does your tool fit," the answer is **"this is a Level 3 fair value workflow."**

### Why provenance matters in audit

An auditor's signature on a report has personal liability attached. They cannot sign off on a number they can't trace back to inputs and methodology. This is *why* "audit trail" is the key non-functional requirement — it's not a nice-to-have, it's the whole job. Every design choice in our tool flows from this:

- Pydantic models with explicit schemas → the inputs are typed and documented.
- `Citation` and `Assumption` are first-class output objects → every number can be drilled into.
- The `TriangulatedValuation` echoes the original request → the report is fully self-contained.
- JSON output is the machine-readable artifact; Markdown is the human-readable one. Both can be archived as the immutable record of the analysis.

### Why multiple methods (the ASC 820 angle)

ASC 820 paragraph 820-10-35-24B: *"In some cases, a single valuation technique will be appropriate... [but] when there is no quoted price in an active market, it is sometimes appropriate for an entity to use multiple valuation techniques..."* and the entity is *"required to evaluate the results (or respective indications of fair value) of all techniques and weigh them, as appropriate."*

(See README "Sources & references" for the codification link. Verified verbatim via Deloitte DART, May 2026. **Note:** earlier drafts of this document cited paragraph 24A — that's the wrong paragraph (24A is about the *objective* of valuation techniques and the three approaches; 24B is the one about multiple techniques). 24B is the correct cite and is also stronger — it explicitly endorses *weighting* the techniques, which is what the triangulator does.)

This is the formal grounding for triangulation. Mention this almost verbatim if you can — shows you actually read the standard, not just intuited the right approach.

---

## 7. Technical talking points

Concepts to be ready to discuss when the conversation goes architectural.

### Strategy pattern

`ValuationMethod` is an abstract base class. Each method (Comps, DCF, Last Round) is a concrete implementation. The Triangulator only knows about the interface, never the concrete classes. This is the textbook **strategy pattern** and it's why adding a fourth method is a 1-file change.

### Why Pydantic specifically

- Validation at the boundary (request comes in → either it parses or it 422s with a clear error).
- Schema generation for free → FastAPI publishes OpenAPI docs at `/docs` automatically.
- Forces typed I/O, which makes the audit-trail story concrete (the report's structure is a schema, not a convention).

### Why `Decimal` not `float`

Floating-point math is wrong for money. `0.1 + 0.2 != 0.3` in float. In an audit context this would be a credibility-killer. `Decimal` is exact. The cost is mild verbosity (`Decimal("0.21")` instead of `0.21`).

### Why `Protocol` for providers

`Protocol` is structural typing in Python — anything with the right methods satisfies it, no inheritance required. Lets us swap mock providers for real ones without changing any consuming code. Easier to test, easier to extend.

### Stateless design

The API holds no state between requests. Same request → same response (modulo the timestamp). This makes every output **reproducible**, which matters for audit replay.

### Confidence as a first-class output

Each method derives its own confidence from documented signals (round age for Last Round, peer count for Comps, projection length for DCF). The Triangulator does no magic — it normalizes confidences to weights. This means the *weighting decision is auditable* alongside the value itself.

---

## 8. Things we explicitly chose NOT to pursue

Clearly labeled so you can speak to each in the interview as a deliberate scope choice (not an oversight).

### Methodology choices we rejected

- **Single-method implementation (e.g., Comps only).** Faster to build but a much weaker walkthrough. Single-method tools don't show off the abstraction or match real audit practice.
- **DCF without other methods.** Would have been 100 lines of arithmetic on a JSON projection, with no interesting workflow story. We include DCF only as one input to triangulation.
- **Statistical confidence intervals over the method outputs.** Would require distributional assumptions we can't defend with three data points. We use min/max + dispersion instead — more honest.
- **Weighted envelope for the range** (instead of min/max). Mathematically tidier but dishonestly hides model disagreement. Audit prefers conservatism in fair-value ranges.

### Features we rejected

- **Real API integrations** (Yahoo Finance, FRED, etc.). Adds dependency risk, rate-limit handling, credentials management. Prompt explicitly endorses mocking. We hide providers behind interfaces so a real implementation is a future drop-in.
- **Persistence / database.** Stateless service is simpler, the prompt doesn't require it, and a real audit system would persist via a content-addressed report store anyway (which is a much more interesting design conversation than "we put it in Postgres").
- **Authentication / multi-tenancy.** Out of scope. Mention as "obviously needed for production" if asked.
- **Multi-currency.** All values assumed USD. A real implementation would need an FX provider with historical rates.
- **Peer-similarity scoring beyond exact sector match.** A real Comps implementation would do fuzzy matching on size, growth rate, geography, business model. We use exact sector match because the *workflow* is what's being demonstrated, not the matching algorithm.
- **Per-sector dispersion threshold calibration.** Mature companies' methods should agree more than early-stage. Calibrating dispersion thresholds per sector requires historical review data we don't have.
- **Content-addressed immutable report store.** Real audit immutability requires hashing reports and storing them where they can't be edited. Mention as future work.
- **Batch processing of multiple companies.** Trivial extension if asked — call the same engine in a loop.
- **PDF report generation.** Markdown is fine for the take-home; PDF is a serialization detail.

### Open decisions (resolved)

- **DCF tax adjustment** — RESOLVED: added `tax_rate` field with default 0.21 (US corporate). Auditor-overridable. See §5a for tradeoffs.
- **DCF sensitivity analysis** — RESOLVED: planned as T15 (Phase 3, post-Phase 2). 3×3 grid replacing the hardcoded ±20–25% range.
- **Per-method outlier detection** — RESOLVED: added as T17 stretch. Complements (does not replace) the dispersion flag.
- **Streamlit UI (T16)** — gated stretch; ship only if Phases 0–2 finish cleanly.

---

## 9. Likely interview questions and how to handle

Prepare a 2–3 sentence answer for each.

### Methodology

- **"Why three methods?"** ASC 820 encourages triangulation. Single methods miss model disagreement. The interface makes adding a fourth trivial.
- **"What if the comp set is bad / there are no good public comps?"** CompsMethod's confidence drops with peer count. With < 3 peers it returns low confidence and gets de-weighted. The auditor sees this in the report and can either accept the de-weighting or use the manual override.
- **"What about a sector with no public comps at all?"** `is_applicable` returns False. The Triangulator runs whatever methods *are* applicable. If only Last Round qualifies, the report is honest about being a single-method estimate.
- **"Why include DCF for early-stage companies if it's known to be unreliable?"** Two reasons: it provides an intrinsic-value perspective independent of public markets, and its confidence formula self-deweights when projections are short or sparse — so when the inputs are weak, it doesn't dominate.
- **"What if all methods disagree (high dispersion)?"** The dispersion flag fires and the report explicitly flags it for human review. The auditor can apply judgment via the manual weight override.
- **"What's the failure mode of weighted averaging?"** Two methods saying $100M with high confidence + one saying $200M with low confidence pulls the average up. We mitigate by surfacing per-method results and the dispersion metric, but a determined adversarial input could still bias the headline number. Real mitigation would be the auditor override.

### Architecture

- **"Why Python over [Go / Java / Node]?"** Lingua franca for finance/data. Pydantic specifically. Interviewers in this space are fluent. (If they push on perf: "stateless service, low-throughput audit workflow — Python is plenty fast.")
- **"How does this scale?"** Stateless API → horizontal scaling is trivial. The interesting bottleneck is the data providers; in a real implementation those would be the things that need caching/batching.
- **"How would you persist results?"** Content-addressed store: hash the JSON report, write it once, never mutate. Each report cites the hash of the report it supersedes — full audit lineage. We didn't build it because the prompt is stateless.
- **"How do you guarantee the report can't be tampered with?"** Hash + immutable store. Optionally sign with the auditor's key.

### Code quality

- **"Walk me through the request flow."** Request hits API → Pydantic validates → Triangulator picks applicable methods → each method runs and returns a self-describing result → Triangulator computes weights, point, range, dispersion → result rendered to JSON or Markdown.
- **"How do you test this?"** Unit tests per method against fixed inputs. Triangulator tests use fake methods (no real method dependencies). Integration tests run the full CLI/API on sample fixtures.
- **"What's your error-handling strategy?"** Pydantic at the boundary catches malformed input. Methods that lack inputs return `is_applicable=False` rather than erroring. The Triangulator raises `NoApplicableMethodError` if no method applies — an explicit, named failure mode.

### Honest critique

- **"What's the weakest part of your design?"** Probably the hardcoded range factors and the dispersion threshold — both are heuristics without empirical grounding. The principled upgrades are sensitivity analysis (for ranges) and historical calibration (for the threshold), and both would need data we don't have.

---

## 10. Cheat sheet — formulas at a glance

```
EV ≈ market_cap + debt − cash

EBITDA = revenue − operating_expenses (excl. D&A)
EBIT   = EBITDA − D&A
NOPAT  = EBIT × (1 − tax_rate)

FCF (textbook)  = EBIT × (1 − tax) + D&A − capex − ΔNWC
FCF (our DCF)   = EBITDA × (1 − tax) − capex − ΔNWC   [tax defaults to 0.21; no D&A tax shield modeled]

DCF EV = Σ [ FCF_t / (1+r)^t ]  for t=1..N
       + TV / (1+r)^N

TV (Gordon)  = FCF_final × (1+g) / (r − g)

Comps fair value = median(EV_i / Revenue_i) × target_revenue

Last Round fair value = last_post_money × (1 + index_return)
  where index_return = price_now / price_at_round − 1

Confidence (Last Round) = max(0, 1 − age_days / 730)
Confidence (Comps)      = min(1, n_peers / 8)
Confidence (DCF)        = min(1, projection_years / 5) × completeness_ratio

Triangulated point = Σ w_i × point_i        [normalized weights]
Triangulated low   = min(low_i)
Triangulated high  = max(high_i)
Dispersion         = (high − low) / point
Dispersion flag    = dispersion > 0.5
```

---

## 11. Notes-to-self (add as we work)

*(Use this section to jot anything that comes up during implementation — surprising design choices, things you want to research more, questions for the team.)*

### Phase 0 (scaffold + models + contracts)

**Tooling deltas from `PLAN.md`** (resolved up-front with the user):
- `uv` instead of `pip + venv`. Single fast binary, deterministic lockfile via `uv.lock`, `uv sync` handles project + dev deps in one shot. No effect on output, only dev-loop speed and reproducibility.
- `ruff` for both lint **and** format. The plan literally said "ruff/black"; ruff's formatter matches Black's style at ~50× the speed, so one tool replaces two with no style change. Config lives entirely in `pyproject.toml`.
- Python `>=3.12` target (gets PEP 695 type aliases and `@override`). `.python-version` pinned to `3.13` to use the locally available interpreter and skip a download — `requires-python = ">=3.12"` keeps the project portable.

**Talking point:** "I made conservative tooling deltas from the plan. Both are strictly faster on the dev loop and neither changes correctness or output. Documented up-front so they're defensible."

**Decimal JSON serialization — `DecimalStr`**: every money field in `models/types.py` is `Annotated[Decimal, PlainSerializer(str, when_used="json")]`. Pydantic v2's default emits `Decimal` as a JSON *number*, which silently downgrades to float on parse and can lose precision. Forcing JSON to a string preserves exact value through round-trips. This is verified by `test_decimal_precision_survives_json_roundtrip` (15-digit precision survives) and `test_decimal_serialized_as_string_in_json`.

**Talking point:** "Tiny choice that prevents an entire class of finance-domain bugs. Anyone who does `model_dump_json()` and re-parses gets the exact same Decimal back, byte-for-byte."

**Frozen models for value types**: `PortfolioCompany`, `Assumption`, `Citation`, `FinancialProjection`, and `Comp` are `frozen=True`. They're immutable inputs — accidentally mutating them post-construction is always a bug. Mutable result types (`MethodResult`, `TriangulatedValuation`) are not frozen because they may be assembled incrementally in the Triangulator (T7).

**`@runtime_checkable` on the Protocols**: lets tests confirm structural conformance via `isinstance(obj, CompsProvider)` cheaply. Doesn't constrain real implementations — Protocol still doesn't require inheritance.

**Boundary discipline — no model-layer "must satisfy at least one method" guard**: deliberately *not* added at the request model. `PLAN.md` §5.5 puts that in the Triangulator (`NoApplicableMethodError`). Putting it on the model would mean the model knows about methods, breaking layering. Talking point on layering: "models know nothing about methods; methods declare applicability; the engine raises the named error."

**Verification status**: `make check` passes — `ruff check`, `ruff format --check`, `mypy --strict` (with `pydantic.mypy` plugin), and `pytest` (22 tests) all green. Phase 0 contracts are locked.

### Phase 1 (methods + engine + reports)

**Three parallel streams off Phase 0**: Stream A (Comps + MockCompsProvider + fixture), Stream B (LastRound + MockMarketIndexProvider + fixture), Stream C (DCF + Triangulator + report writers). Each landed as its own PR (#2, #3, #4) with trivial `__init__.py` re-export rebases between merges. Final test count: 100, all green.

**Why nearest-prior date lookup for the index** (vs. linear interpolation): the fixture is monthly NASDAQ closes — interpolating a daily level *between* monthly anchors implies more precision than the data carries. Nearest-prior is the standard backstop in market-data providers when the requested date isn't a trading day, and it's defensibly conservative (returns a known close, never a synthetic value). The choice is emitted as an explicit `Assumption` ("Index lookup strategy: nearest-prior date") so an auditor reviewing the artifact sees it. Linear interpolation would be a one-line swap if a customer asked for it.

**Why ±22.5% midpoint for DCF range** (hardcoded, range = `[point × 0.775, point × 1.225]`): pure placeholder. The right answer is T15's 3×3 sensitivity grid (discount_rate ± 1pp × terminal_growth ± 0.5pp, 9 DCFs, take min/max as range, midpoint as point). The placeholder is emitted verbatim as an `Assumption` ("Range factor: ±22.5% (placeholder for T15 sensitivity grid)") so it can't be silently shipped. Talking point: "the range is *intentionally* a known-bad shortcut; the assumption tells the auditor exactly that."

**`is_applicable` queries the provider** (CompsMethod especially): `is_applicable` checks `len(provider.get_comps(sector)) >= 1`, and LastRoundMethod's checks index coverage of both dates. This means a method's applicability can depend on data, not just request shape. The alternative — let `value()` throw mid-flight — would have made the Triangulator's "filter to applicable" contract a lie. Cost is one extra provider hit per applicability check, which is fine for an in-memory mock. For a real-API provider you'd add a thin cache or shift to a "try-and-fall-back" pattern in the Triangulator.

**Equal-weight fallback when all confidences are zero**: signalled implicitly via `MethodWeight.raw_confidence=0` paired with non-zero `normalized_weight=1/n` and `overridden=False`. We considered injecting a synthetic note onto the first `MethodResult`, but that would mutate per-method outputs to communicate an engine-level fallback — wrong layer. Documented in the Triangulator module docstring instead. Should be rare in practice (at least one method usually returns positive confidence on real inputs).

**T9 fixtures (`examples/inputs/*.json`)**: four request shapes — `comps_only`, `last_round_only`, `dcf_only`, `full`. The `full.json` example deliberately produces a dispersion of ~2.5 (flag=True) — methods disagree because a SaaS company at $500M revenue lands very differently under public-multiple comps vs. a 2023 round adjusted by NASDAQ vs. DCF on its projected EBITDA path. That's a feature, not a bug: it's the demo of "the system surfaces method disagreement to the auditor instead of smoothing it away."

### Phase 2 (API + CLI + integration tests)

**Why `?format=json|markdown|both` instead of `/valuations/{id}/report`**: the service is stateless by design (§7), so there is no `id` to fetch later. Collapsing the report endpoint into a query param keeps a single entry point, lets the response Content-Type vary with the format (`application/json` vs. `text/markdown`), and avoids the wrapping tax for the common single-format case. The `both` mode pays a small envelope cost only when explicitly requested. The CLI's `--format` flag mirrors the API verbatim — same vocabulary across both surfaces.

**Why CLI defaults to stdout, not files**: pipe-friendly by default (`vc-audit value -i in.json | jq .point_estimate`, `… --format markdown | less`). `--output-dir` is the explicit-artifact mode an auditor would use to file an audit trail. Treating disk as the opt-in keeps quick checks frictionless without sacrificing the artifact-on-demand workflow.

**Method self-description (`describe()` classmethod)**: each strategy class owns its `name`, `description`, and `required_inputs`. `GET /methods` and `vc-audit methods` both call `default_method_descriptors()`, which calls `Method.describe()`. Consistent with the rest of the audit-trail design — every output knows what produced it. Adding a new method means adding three `ClassVar`s alongside the existing one; the API and CLI surfaces pick it up automatically through the factory.

**`engine/factory.py` as the single composition root**: both `cli.py` and `api/server.py` import `build_default_triangulator()` from there. The API caches it under `functools.lru_cache` for warm restarts; the CLI re-creates it per invocation (cheap — mocks parse a small JSON fixture once). Tests can still construct alternative `Triangulator`s directly when they need different methods or providers; the factory is convenience, not a barrier.

**TestClient (sync, httpx-backed) over async test patterns**: the API has no async work — handlers are sync, the engine is sync, providers are sync. A sync `TestClient` keeps test code linear and skips `pytest-asyncio`. Talking point: "async-by-default is a cargo-culted FastAPI pattern; we let the workload pick."

**Parity test (`test_integration_parity.py`)**: drives `examples/inputs/full.json` through both the API and the CLI, parses both JSON outputs, strips run-time fields (`generated_at`, per-citation `retrieved_at`), and asserts deep equality on everything else. Catches any future drift if either presentation surface starts massaging the result. Talking point: "CLI and API are paper-thin wrappers over the same engine — for any input, the JSON artifact and the human-readable report are byte-identical between surfaces."

**Click 8.2 deprecation gotcha**: `CliRunner(mix_stderr=False)` was removed in Click 8.2; stderr is now always captured separately. Tests use the no-arg constructor; `result.stderr` is independently asserted-on for error-path tests.

**Bundled example resolution**: `vc-audit example` reads `examples/inputs/full.json` via a project-root-relative path resolved from `__file__`. Works for `uv run` and editable installs; a non-editable install would need package-data wiring (`importlib.resources`), which is out of scope for the take-home. The CLI fails loudly with an exit-2 + stderr message if the file is missing, rather than silently printing nothing.

**Verification status**: `make check` passes (ruff + ruff format-check + mypy --strict + pytest). Test count went from 100 → 127 (+27): 11 API tests, 9 CLI tests, 1 parity test, with 3 of the API/CLI tests parameterized over all 4 fixture files. Live-server smoke tests (`/health`, `/methods`, `/valuations` × 3 formats, 422 paths) all green; CLI `--output-dir` mode writes both `.json` and `.md` for the full fixture.

### Phase 3 (T17 outlier detection)

**Why keep `dispersion_flag` AND add outlier names**: they answer different questions. `dispersion_flag` is the aggregate "do the methods disagree?" signal — one boolean derived from `(high − low) / point`. `outlier_method_names` answers "where is the disagreement coming from?" by naming the specific method(s) whose point estimate sits >2× or <0.5× the median across applicable methods. The reviewer reads the headline once and knows both whether to drill in *and* where to drill in. Replacing one with the other would lose information; keeping both costs two lines of headline text.

**Why `default_factory=list` is non-negotiable**: sibling Phase 3 PRs (T15 sensitivity grid, T16 Streamlit UI) construct `TriangulatedValuation` instances without knowing about this field. A required field would force them to rebase against breaking changes; a defaulted field lets them pick up the new column passively when they merge. The Pydantic-level `default_factory` (vs. a class-level `[]`) is a mutable-default nicety — every instance gets its own list rather than sharing one.

**Why n<3 returns empty**: the median is meaningless with fewer than three samples. With n=1 the sole estimate trivially *is* the median, so it can never exceed itself. With n=2 the larger always exceeds 2× of `(a+b)/2` when `b > 3a`, which would flag the larger value in any "they disagree" pair — that's just a worse restatement of the dispersion flag. The 2× / 0.5× thresholds only carry information when there's a genuine middle to compare against. Returning `[]` instead of erroring keeps the engine happy on single-applicable-method runs (Comps-only, DCF-only).

**Why method *names*, not richer structure**: the per-method block already carries the gory detail — point estimate, range, confidence, weight, overridden flag, assumptions, citations. The headline's job is to point a finger; a list of names is the terse audit-trail-friendly way to do that. A richer structure (deviation factor, direction, etc.) would duplicate information already three rows down in the per-method table. We chose terseness; the reader can compute "by how much" from the table.

**Threshold choice (2× / 0.5×)**: symmetric in log-space (i.e., `multiplier > 2 or multiplier < 1/2`), which is the right family for ratio data — a method valuing the company at half the median is just as off as one valuing it at double, and a constant absolute-dollar threshold would be wrong as soon as the company size changes. Heuristic, like the 0.5 dispersion threshold; in a calibrated product these would come from historical reviewer-overrule data.

### Phase 3 (T15 sensitivity grid)

**Why midpoint of min/max as the point estimate, not the center cell.** The grid exists precisely *because* a single cell is a fragile answer for DCF — moving the discount rate 1pp can shift the result 15–20%. If the point estimate is the unperturbed center cell, the range honestly reflects sensitivity but the headline number doesn't — the reader sees one number that pretends to be "the answer" plus a separate range that contradicts that pretense. The midpoint of `[min, max]` is the natural expected value of a uniform distribution over the grid corners; it's a function of the whole grid, so when corners shift the point shifts with them. Tradeoff: the midpoint diverges from the unperturbed EV, and the relationship `point ≠ unperturbed_ev` may surprise a reviewer who thinks "DCF gives one number and this is it." We accept that — the whole point of the grid is to refuse to pretend any single cell is "the answer." The `_compute_ev` helper at center is still exported to tests so the unperturbed EV remains inspectable as a sanity-check anchor.

**Why skip on Gordon violation rather than clamp `g = r − ε`.** When the perturbed `(r' − g')` approaches zero, the Gordon terminal value `FCF × (1 + g) / (r − g)` blows up. Clamping `g = r − ε` would silently distort the cell value by an arbitrary amount tied to ε's choice — the result would still numerically resolve, but it'd be meaningless and would propagate into the min/max bounds and the midpoint. Skipping the cell degrades gracefully: the assumption rationale flags exactly how many cells were skipped (`"N cell(s) skipped (Gordon stability: g >= r)"`), so an auditor reading the report sees the warning surface explicitly. The alternative of refusing the entire grid when any cell violates would be too brittle — a reasonable input with `g` close to `r` (e.g., a low-discount-rate stable business) might well have one or two cells violate while seven remain perfectly valid.

**The all-cells-skipped fallback and why it should never fire in practice.** `is_applicable` enforces `g < r` at the center, which means the center cell `(dr=0, dg=0)` is always valid for a request that passes the gate. With the grid deltas (-0.01, 0, +0.01) for `r` and (-0.005, 0, +0.005) for `g`, the only way to skip every cell is `g >= r + 0.015` — which fails the center Gordon check, so `is_applicable` would refuse. The fallback (compute center cell only, set `low = high = point = center`, label rationale "fallback: full grid skipped") therefore exists strictly for the case where some pathological input bypasses `is_applicable` (e.g., a future caller that constructs a `MethodResult` without checking applicability first). It's dead code on the happy path but defensive belt-and-suspenders for the engine layer. The test for it explicitly bypasses the gate by calling `value()` on a request where `g > r`.

**Test-case adjustments.** The point-estimate definition changed from "unperturbed EV" to "midpoint of grid bounds," so any test that asserted `result.point_estimate == ev` had to be reworked. The new pattern is to compute the 9 cells inline using the same `Decimal` precision via a private helper (`_expected_grid_midpoint`) and compare against `result.point_estimate / low / high`. The unperturbed EV is now exercised through a separate test (`test_grid_center_cell_equals_unperturbed_ev`) that calls `_compute_ev(projections, r, g, tax)` directly — it's the same number the old test asserted on, just relabeled. Four new tests were added: center-cell equivalence, narrower-than-placeholder range for stable inputs, skip-counting when `g` is close to `r`, and the all-cells-skipped fallback. Test count: 138 (was 133), all green; `make check` passes ruff + format-check + mypy --strict + pytest.

### Phase 3 (T16 Streamlit UI)

**Why in-process, not HTTP-to-FastAPI**: the Streamlit page imports `build_default_triangulator()` directly and runs the engine in the Streamlit Python process. The take-home prompt explicitly endorses "CLI is fine, or simple web frontend"; we already have CLI + FastAPI, so the UI is the human-facing demo and the API is the integration-shape demo — different audiences, no overlap. Going in-process means one less moving part for a live demo (no `make dev` + `make ui` two-process dance), and the UI picks up engine changes (T15 grid, T17 outliers) automatically the moment they merge. If we ever wanted the UI to talk over HTTP we'd swap one helper; the boundary is clean. Talking point: "the UI is the human surface, the API is the service surface — both are paper-thin over the same engine."

**Why an optional-dependency group (`[project.optional-dependencies] ui`)**: streamlit pulls a sizeable transitive set (pyarrow, pillow, tornado, …) that nobody using the CLI or API needs. Putting it under `pip install vc-audit[ui]` / `uv sync --extra ui` keeps the default install slim, keeps CI fast (`make check` runs in the dev group only), and avoids surprising import-cost for downstream users. The `make ui` target wires `--extra ui` so the demo path is one command.

**Why split helpers into `_helpers.py`**: `app.py` imports `streamlit` at module top, which means `from vc_audit.ui.app import …` would fail for anyone without the `ui` extra. That includes `make check`, since the dev group doesn't pull streamlit. Splitting `load_example`, `form_to_request`, and `run` into `_helpers.py` keeps the helpers importable and unit-testable in isolation, while `app.py` stays as the streamlit-only entry point that `streamlit run` consumes. Tests import from `vc_audit.ui._helpers` directly.

**Test boundary — pure helpers only**: Streamlit's runtime is hard to drive without `streamlit.testing.v1.AppTest`, which is overkill for a demo. The unit suite covers (a) every bundled fixture loads + parses, (b) unknown fixture names raise loudly, (c) the form-state → request round-trip holds for `full.json`, and (d) the `_run` helper produces a positive point estimate and a markdown report containing the company name. The streamlit page itself was smoke-tested manually via `streamlit run` and a one-off `AppTest` driver (default state, "Run" button on the Load-example mode, and switching to Form / Paste JSON modes — all rendered without exceptions). The integration test going forward is "does `make ui` open and render?" — manual.

**Structured form vs. paste-JSON tradeoff**: three input modes serve different demo flows. **Load example** is the fastest path — pick a fixture, hit Run, see the report; useful for the live demo and for showing dispersion behavior on `high_dispersion.json`. **Form** is the discoverability mode — every `ValuationRequest` field is a labeled widget with a sensible default, so a viewer learns the input schema without reading code. **Paste JSON** is the escape hatch for anyone who wants to drop in a fixture verbatim or roundtrip from another tool. All three feed a single `ValuationRequest` and the same `_run` call, so the rendering path is shared.

**Verification status**: `make check` passes (ruff + ruff format-check + mypy --strict + pytest). Test count: 133 → 143 (+10) — six parameterized fixture tests + unknown-name + on-disk-vs-tuple parity + form round-trip + run smoke. `make ui` was manually verified: streamlit boots cleanly, the page returns HTTP 200, and the AppTest harness drives the "Load example → Run" path on `full.json` (the demo flow) producing a markdown report with no exceptions.

### Phase 3 (T14 example outputs)

The repo now ships rendered artifacts under `examples/outputs/` — one `.json` and one `.md` for each of the six bundled fixtures, regenerated post-T15 and post-T17 so they include the new "Sensitivity grid" assumption block (in fixtures that exercise DCF) and the per-method "Outlier methods:" headline line where applicable. A reviewer can read the artifacts without running anything; the `make examples` target keeps them refreshable in one command.

**Why output filenames are derived from the input fixture stem, not the company slug**: the original `--output-dir` CLI mode names files after `slug(company.name)`, which collides when two fixtures reference the same portfolio company (`full.json` and `with_overrides.json` both target Atlas Cloud Inc.). The collision silently overwrote one of the two outputs, hiding the override-comparison demo. The make target side-steps this by piping the CLI's stdout to `examples/outputs/$(basename input).{json,md}`, giving 1:1 input-to-output correspondence. Two CLI invocations per fixture (one per format) is fine for a build target — the cost is ~12 cold-starts and the output is byte-stable across runs.

**Why `examples/outputs/` is now tracked in git**: it was previously gitignored (Phase 0 default for "generated reports"), but for a take-home submission the artifacts are the demo. Removed the gitignore entry; `make examples` is re-runnable so a reviewer can verify the artifacts match what the engine produces.

**Spot-check status**: every DCF-applicable fixture (`dcf_only`, `full`, `high_dispersion`, `with_overrides`) carries the "Sensitivity grid" assumption; `full.md` and `with_overrides.md` flag `dcf` as the outlier method, `high_dispersion.md` flags `last_round`, and `full.md`'s dispersion is 2.5088 (matches the design note above). The two non-DCF fixtures (`comps_only`, `last_round_only`) intentionally have no sensitivity-grid assumption since DCF doesn't run for them.

### Phase 3 (T13 README)

Replaced the Phase 0 scaffolding stub with a take-home submission front door — eight sections covering what the tool is, the methodology table, a thinned architecture diagram (the full one lives in `PLAN.md` §3), a Quickstart with the five make targets, a per-surface usage block (CLI / API / UI), a flat list of the load-bearing design decisions, a "what I'd do next" section, and a 10-line repo-layout tree. Target was the prompt's "max 1 page" — the result is one screenful of markdown.

**Deliberately out of scope**: extensive benchmarking, Docker setup, deployment notes, contribution guidelines, and CI badges. The take-home prompt scope is "structured, auditable workflow" — operations material would dilute the signal that the engine and audit trail are the substance. The README points at `PLAN.md` and `discussion.md` for readers who want the deeper rationale; the trail is one click deep, not buried.

**Why one bundled-pair link rather than every fixture**: the README cites `examples/inputs/full.json` ↔ `examples/outputs/full.md` as the canonical demo pair. Listing all six would compete with the methodology table for the reader's attention; the rest are discoverable via `examples/` and `make examples`.
