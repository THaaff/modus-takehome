# VC Audit Report — Halcyon Robotics

**As-of date:** 2026-03-31
**Generated:** 2026-05-08T00:57:09.580773+00:00

## Headline

_Money values are in $M (millions of US dollars). Confidence and weights are in [0, 1]. Dispersion is a unitless ratio._

- **Valuation point estimate:** $317.25M
- **Valuation range:** $269.66M – $364.84M
- **Dispersion:** 0.3000 (within tolerance)

## Method breakdown

| Method | Point ($M) | Low ($M) | High ($M) | Confidence | Weight | Overridden | Outlier |
|---|---|---|---|---|---|---|---|
| last_round | $317.25M | $269.66M | $364.84M | 12.19% | 100.00% | no |  |

### last_round

**Assumptions:**
- **Reference index:** NASDAQ — Used as a public-market proxy for the period return between last round and as-of date.
- **Range factor:** +/-15% — Basis-risk haircut/expansion to reflect that the chosen index is an imperfect proxy for the company's specific industry beta.
- **Index lookup strategy:** nearest-prior date — Returns the closing level of the most recent entry on or before the requested date. Defensible heuristic in the absence of daily granularity; emit as a known approximation rather than interpolating.
- **Age decay:** 641 days; confidence = max(0, 1 - age/730) — Last-round signal degrades as the round becomes stale; zero confidence at 2 years.

**Citations:**
_Upstream data sources this method drew from. Format: `Source: identifier — description (retrieved timestamp)`._
- **MarketIndexProvider:** mock_nasdaq_v1 — NASDAQ 17732.60 on 2024-06-28 -> 17580.12 on 2026-03-31 (retrieved 2026-05-08T00:57:09.580624+00:00)

## Skipped methods

_Registered methods that did not run for this request, and why. Useful for explaining why the triangulated estimate is leaning on a subset._

- **comps:** Company sector is missing — comps requires a sector to match peers.
- **dcf:** DCF requires at least 2 years of financial projections.

## Request (echoed)

```json
{
  "company": {
    "name": "Halcyon Robotics",
    "sector": null
  },
  "revenue": null,
  "ebitda": null,
  "last_post_money_valuation": "320.0",
  "last_round_date": "2024-06-28",
  "reference_index": "NASDAQ",
  "projections": null,
  "discount_rate": null,
  "terminal_growth_rate": null,
  "tax_rate": "0.21",
  "method_weights": null,
  "as_of_date": "2026-03-31"
}
```

