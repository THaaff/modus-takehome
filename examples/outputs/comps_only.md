# VC Audit Report — Northwind FinTech Inc.

**As-of date:** 2026-03-31
**Generated:** 2026-05-08T00:57:08.784874+00:00
**Sector:** FinTech

## Headline

_Money values are in $M (millions of US dollars). Confidence and weights are in [0, 1]. Dispersion is a unitless ratio._

- **Valuation point estimate:** $1,278.26M
- **Valuation range:** $549.72M – $2,072.92M
- **Dispersion:** 1.1916 (FLAG)

## Method breakdown

| Method | Point ($M) | Low ($M) | High ($M) | Confidence | Weight | Overridden | Outlier |
|---|---|---|---|---|---|---|---|
| comps | $1,278.26M | $549.72M | $2,072.92M | 50.00% | 100.00% | no |  |

### comps

**Assumptions:**
- **Multiples used:** EV/Revenue and EV/EBITDA — EV/Revenue applied whenever target revenue and >=1 peer revenue are present; EV/EBITDA additionally applied when target EBITDA and >=2 peers' EBITDA are positive.
- **EV/Revenue median multiple:** 8.50x — Median across sector peers; 25/75 percentile drives low/high.
- **EV/EBITDA median multiple:** 23.76x — Median across sector peers with positive EBITDA.
- **Peer count:** 4 — Number of sector-matched peers found in the comps universe; drives confidence via min(1, n/8).

**Citations:**
_Upstream data sources this method drew from. Format: `Source: identifier — description (retrieved timestamp)`._
- **CompsProvider:** mock_universe_v1 — Peer set: MA, PYPL, SQ, V (sector=FinTech, n=4) (retrieved 2026-05-08T00:57:08.784725+00:00)

## Skipped methods

_Registered methods that did not run for this request, and why. Useful for explaining why the triangulated estimate is leaning on a subset._

- **last_round:** Last post-money valuation is missing — last_round needs a prior round price.
- **dcf:** DCF requires at least 2 years of financial projections.

## Request (echoed)

```json
{
  "company": {
    "name": "Northwind FinTech Inc.",
    "sector": "FinTech"
  },
  "revenue": "210.0",
  "ebitda": "32.5",
  "last_post_money_valuation": null,
  "last_round_date": null,
  "reference_index": "NASDAQ",
  "projections": null,
  "discount_rate": null,
  "terminal_growth_rate": null,
  "tax_rate": "0.21",
  "method_weights": null,
  "as_of_date": "2026-03-31"
}
```

