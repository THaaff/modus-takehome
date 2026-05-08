# VC Audit Report — Lumina Analytics

**As-of date:** 2026-03-31
**Generated:** 2026-05-08T00:57:09.378698+00:00
**Sector:** SaaS

## Headline

_Money values are in $M (millions of US dollars). Confidence and weights are in [0, 1]. Dispersion is a unitless ratio._

- **Valuation point estimate:** $898.73M
- **Valuation range:** $246.36M – $1,191.25M
- **Dispersion:** 1.0514 (FLAG)
- **Outlier methods:** last_round

## Method breakdown

| Method | Point ($M) | Low ($M) | High ($M) | Confidence | Weight | Overridden | Outlier |
|---|---|---|---|---|---|---|---|
| comps | $763.42M | $584.19M | $947.69M | 50.00% | 33.33% | no |  |
| last_round | $289.83M | $246.36M | $333.31M | 0.00% | 0.00% | no | yes |
| dcf | $966.39M | $741.52M | $1,191.25M | 100.00% | 66.67% | no |  |

### comps

**Assumptions:**
- **Multiples used:** EV/Revenue and EV/EBITDA — EV/Revenue applied whenever target revenue and >=1 peer revenue are present; EV/EBITDA additionally applied when target EBITDA and >=2 peers' EBITDA are positive.
- **EV/Revenue median multiple:** 13.39x — Median across sector peers; 25/75 percentile drives low/high.
- **EV/EBITDA median multiple:** 56.94x — Median across sector peers with positive EBITDA.
- **Peer count:** 4 — Number of sector-matched peers found in the comps universe; drives confidence via min(1, n/8).

**Citations:**
_Upstream data sources this method drew from. Format: `Source: identifier — description (retrieved timestamp)`._
- **CompsProvider:** mock_universe_v1 — Peer set: CRM, DDOG, NOW, WDAY (sector=SaaS, n=4) (retrieved 2026-05-08T00:57:09.378423+00:00)

### last_round

**Assumptions:**
- **Reference index:** NASDAQ — Used as a public-market proxy for the period return between last round and as-of date.
- **Range factor:** +/-15% — Basis-risk haircut/expansion to reflect that the chosen index is an imperfect proxy for the company's specific industry beta.
- **Index lookup strategy:** nearest-prior date — Returns the closing level of the most recent entry on or before the requested date. Defensible heuristic in the absence of daily granularity; emit as a known approximation rather than interpolating.
- **Age decay:** 790 days; confidence = max(0, 1 - age/730) — Last-round signal degrades as the round becomes stale; zero confidence at 2 years.

**Citations:**
_Upstream data sources this method drew from. Format: `Source: identifier — description (retrieved timestamp)`._
- **MarketIndexProvider:** mock_nasdaq_v1 — NASDAQ 15164.01 on 2024-01-31 -> 17580.12 on 2026-03-31 (retrieved 2026-05-08T00:57:09.378587+00:00)

### dcf

_3x3 sensitivity grid (discount_rate +/- 1pp x terminal_growth +/- 0.5pp) over 5 projection years; range = min/max across 9 valid cells, point = midpoint._

**Assumptions:**
- **Discount rate:** 10.00% — Auditor-supplied WACC proxy.
- **Terminal growth rate:** 3.00% — Long-run nominal growth; must be < discount rate (Gordon stability).
- **Tax rate:** 21.00% — default; auditor can override
- **FCF formula:** EBITDA × (1 − tax) − capex − ΔNWC — No D&A tax shield modeled — slightly conservative.
- **Sensitivity grid:** 3x3 (discount_rate +/- 1pp x terminal_growth +/- 0.5pp) — Range = min/max across 9 valid cells; point = midpoint. 0 cell(s) skipped (Gordon stability: g >= r).
- **Confidence formula:** min(1, 5/5) × completeness_ratio — Saturates at 5 projection years; completeness counts non-zero revenue/ebitda/capex across years (ΔNWC excluded — default is 0).

**Citations:**
_Upstream data sources this method drew from. Format: `Source: identifier — description (retrieved timestamp)`._
- **ValuationRequest:** projections — DCF on 5 projection years; discount=0.10, terminal_growth=0.03, tax=0.21 (retrieved 2026-05-08T00:57:09.378675+00:00)

**Sensitivity grid (EV in $M):**

_Rows: perturbed discount rate (center ±1pp). Columns: perturbed terminal growth (center ±0.5pp). Center cell (auditor-supplied rates) is **bold**._

| discount rate \ terminal growth | 2.50% | 3.00% | 3.50% |
|---|---|---|---|
| 9.00% | $1,019.25M | $1,098.08M | $1,191.25M |
| 10.00% | $861.46M | **$917.93M** | $983.07M |
| 11.00% | $741.52M | $783.56M | $831.21M |

## Request (echoed)

```json
{
  "company": {
    "name": "Lumina Analytics",
    "sector": "SaaS"
  },
  "revenue": "80.0",
  "ebitda": "8.0",
  "last_post_money_valuation": "250.0",
  "last_round_date": "2024-01-31",
  "reference_index": "NASDAQ",
  "projections": [
    {
      "year": 1,
      "revenue": "100.0",
      "ebitda": "10.0",
      "capex": "5.0",
      "change_in_nwc": "3.0"
    },
    {
      "year": 2,
      "revenue": "150.0",
      "ebitda": "25.0",
      "capex": "5.0",
      "change_in_nwc": "3.0"
    },
    {
      "year": 3,
      "revenue": "220.0",
      "ebitda": "50.0",
      "capex": "5.0",
      "change_in_nwc": "3.0"
    },
    {
      "year": 4,
      "revenue": "320.0",
      "ebitda": "80.0",
      "capex": "5.0",
      "change_in_nwc": "3.0"
    },
    {
      "year": 5,
      "revenue": "450.0",
      "ebitda": "120.0",
      "capex": "5.0",
      "change_in_nwc": "3.0"
    }
  ],
  "discount_rate": "0.10",
  "terminal_growth_rate": "0.03",
  "tax_rate": "0.21",
  "method_weights": null,
  "as_of_date": "2026-03-31"
}
```

